import os
from kfp import dsl, compiler
from kfp.kubernetes import mount_pvc, use_secret_as_env

MOUNT_PATH = "/opt/app-root/src"
WORKDIR = "/opt/app-root/src/workflows/code_understanding"

DATA_INDEXING_IMAGE = os.environ.get("DATA_IDX_IMG", "")

GIT_SECRET_NAME = "git-credentials"
GIT_SECRET_ENV_VARS = {"GIT_USERNAME": "GIT_USERNAME", "GIT_TOKEN": "GIT_TOKEN"}

LLM_SECRET_NAME = "code-understanding-env"
LLM_ENV_VARS = {
    "GRAPHRAG_LLM_TOKEN":            "GRAPHRAG_LLM_TOKEN",
    "GRAPHRAG_LLM_ID":               "GRAPHRAG_LLM_ID",
    "GRAPHRAG_LLM_API_BASE":         "GRAPHRAG_LLM_API_BASE",
    "GRAPHRAG_LLM_PROVIDER_GRAPHRAG": "GRAPHRAG_LLM_PROVIDER_GRAPHRAG",
    "EMBED_LLM_TOKEN":               "EMBED_LLM_TOKEN",
    "EMBED_LLM_API_BASE":            "EMBED_LLM_API_BASE",
    "EMBED_LLM_ID":                  "EMBED_LLM_ID",
    "EMBED_LLM_PROVIDER_GRAPHRAG":   "EMBED_LLM_PROVIDER_GRAPHRAG",
}


@dsl.container_component
def git_clone_step(repo_url: str, repo_ref: str):
    return dsl.ContainerSpec(
        image=DATA_INDEXING_IMAGE,
        command=["sh", "-c"],
        args=[(
            'if [ -n "$GIT_TOKEN" ]; then '
            "git config --global credential.helper "
            "'!f() {{ echo username=$GIT_USERNAME; echo password=$GIT_TOKEN; }}; f'; "
            'fi && '
            f'git clone {{repo_url}} {MOUNT_PATH} && '
            f'cd {MOUNT_PATH} && git checkout {{repo_ref}}'
        ).format(repo_url=repo_url, repo_ref=repo_ref)],
    )


@dsl.container_component
def extract_step(index_tar: str):
    return dsl.ContainerSpec(
        image="registry.access.redhat.com/ubi9/ubi-minimal",
        command=["sh", "-c"],
        args=[f"cd {WORKDIR} && tar -xzf {{index_tar}}".format(index_tar=index_tar)],
    )


@dsl.container_component
def analysis_step(graphrag_source_path: str, question: str, output_dir: str):
    return dsl.ContainerSpec(
        image=DATA_INDEXING_IMAGE,
        command=["papermill"],
        args=[
            f"{WORKDIR}/data_analysis_graphrag_pipeline.ipynb",
            "/dev/null",
            "--cwd", WORKDIR,
            "-p", "_GRAPHRAG_SOURCE_PATH", graphrag_source_path,
            "-p", "_QUESTION",             question,
            "-p", "_OUTPUT_DIR",           output_dir,
        ],
    )


@dsl.pipeline(
    name="code-analysis-pipeline",
    description="Clone repo, extract GraphRAG index, run analysis notebook, write reports",
)
def code_analysis_pipeline(
    pvc_name:             str = "",
    repo_url:             str = "",
    repo_ref:             str = "main",
    index_tar:            str = "graphrag-index.tar.gz",
    graphrag_source_path: str = f"{WORKDIR}/graph_rag_app/source",
    question:             str = "Which modules would be riskiest to refactor first? Include the fully qualified names.",
    output_dir:           str = f"{WORKDIR}/reports",
):
    clone = git_clone_step(repo_url=repo_url, repo_ref=repo_ref)
    mount_pvc(clone, pvc_name=pvc_name, mount_path=MOUNT_PATH)
    use_secret_as_env(clone, secret_name=GIT_SECRET_NAME, secret_key_to_env=GIT_SECRET_ENV_VARS)

    extract = extract_step(index_tar=index_tar).after(clone)
    mount_pvc(extract, pvc_name=pvc_name, mount_path=MOUNT_PATH)

    analysis = analysis_step(
        graphrag_source_path=graphrag_source_path,
        question=question,
        output_dir=output_dir,
    ).after(extract)
    mount_pvc(analysis, pvc_name=pvc_name, mount_path=MOUNT_PATH)
    use_secret_as_env(analysis, secret_name=LLM_SECRET_NAME, secret_key_to_env=LLM_ENV_VARS)


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    output = os.environ.get(
        "PIPELINE_OUTPUT",
        os.path.normpath(os.path.join(here, "../../../helm/files/code_analysis_pipeline.yaml")),
    )
    compiler.Compiler().compile(code_analysis_pipeline, output)

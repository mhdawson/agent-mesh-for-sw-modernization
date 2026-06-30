import os
from kfp import dsl, compiler
from kfp.kubernetes import mount_pvc, use_secret_as_env

MOUNT_PATH = "/opt/app-root/src"
WORKDIR = "/opt/app-root/src/workflows/code_understanding"

DATA_GENERATION_IMAGE = os.environ.get("DATA_GEN_IMG", "")
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
        image=DATA_GENERATION_IMAGE,
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
def data_generation_step(
    git_repo: str,
    git_branch: str,
    languages: str,
    source_path: str,
    target_path: str,
    max_concurrency: int,
    n_completions: int,
):
    return dsl.ContainerSpec(
        image=DATA_GENERATION_IMAGE,
        command=["papermill"],
        args=[
            f"{WORKDIR}/data_generation_graphrag_pipeline.ipynb",
            "/dev/null",
            "--cwd", WORKDIR,
            "-p", "_GIT_REPO",        git_repo,
            "-p", "_GIT_BRANCH",      git_branch,
            "-p", "_SOURCE_PATH",     source_path,
            "-p", "_TARGET_PATH",     target_path,
            "-p", "_MAX_CONCURRENCY", max_concurrency,
            "-p", "_N_COMPLETIONS",   n_completions,
            "-p", "_LANGUAGES",       languages,
        ],
    )


@dsl.container_component
def data_indexing_step(codebase_path: str, graphrag_source_path: str):
    return dsl.ContainerSpec(
        image=DATA_INDEXING_IMAGE,
        command=["papermill"],
        args=[
            f"{WORKDIR}/data_indexing_graphrag_pipeline.ipynb",
            "/dev/null",
            "--cwd", WORKDIR,
            "-p", "_CODEBASE_PATH",        codebase_path,
            "-p", "_GRAPHRAG_SOURCE_PATH",  graphrag_source_path,
        ],
    )


@dsl.container_component
def tar_step(graphrag_source_path: str):
    return dsl.ContainerSpec(
        image="registry.access.redhat.com/ubi9/ubi-minimal",
        command=["sh", "-c"],
        args=[f"cd {WORKDIR} && tar -czf graphrag-index.tar.gz {{graphrag_source_path}}/output/".format(
            graphrag_source_path=graphrag_source_path
        )],
    )


@dsl.pipeline(
    name="code-understanding-pipeline",
    description="Clone repo, generate GraphRAG metadata, build index, and tar output",
)
def code_understanding_pipeline(
    pvc_name:             str = "",
    repo_url:             str = "",
    repo_ref:             str = "main",
    git_repo:             str = "",
    git_branch:           str = "main",
    languages:            str = '["python"]',
    source_path:          str = "source",
    target_path:          str = "target",
    graphrag_source_path: str = "graph_rag_app/source",
    max_concurrency:      int = 2,
    n_completions:        int = 1,
):
    clone = git_clone_step(repo_url=repo_url, repo_ref=repo_ref)
    mount_pvc(clone, pvc_name=pvc_name, mount_path=MOUNT_PATH)
    use_secret_as_env(clone, secret_name=GIT_SECRET_NAME, secret_key_to_env=GIT_SECRET_ENV_VARS)

    gen = data_generation_step(
        git_repo=git_repo,
        git_branch=git_branch,
        languages=languages,
        source_path=source_path,
        target_path=target_path,
        max_concurrency=max_concurrency,
        n_completions=n_completions,
    ).after(clone)
    mount_pvc(gen, pvc_name=pvc_name, mount_path=MOUNT_PATH)
    use_secret_as_env(gen, secret_name=LLM_SECRET_NAME, secret_key_to_env=LLM_ENV_VARS)

    idx = data_indexing_step(
        codebase_path=target_path,
        graphrag_source_path=graphrag_source_path,
    ).after(gen)
    mount_pvc(idx, pvc_name=pvc_name, mount_path=MOUNT_PATH)
    use_secret_as_env(idx, secret_name=LLM_SECRET_NAME, secret_key_to_env=LLM_ENV_VARS)

    tar = tar_step(graphrag_source_path=graphrag_source_path).after(idx)
    mount_pvc(tar, pvc_name=pvc_name, mount_path=MOUNT_PATH)


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    output = os.environ.get(
        "PIPELINE_OUTPUT",
        os.path.normpath(os.path.join(here, "../../../helm/files/code_understanding_pipeline.yaml")),
    )
    compiler.Compiler().compile(code_understanding_pipeline, output)

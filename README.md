# Agent Mesh for Software Engineering - Code Understanding

Analyze legacy code, build a GraphRAG knowledge graph, and generate an
evidence-based modernization plan on Red Hat OpenShift AI.

Contents
---

- [Overview](#overview)
- [Required Software / Tested with](#tested-with)
- [Installing the Code Understanding Workflow](#installing-the-code-understanding-workflow)
  - [Integrating the Models](#integrating-the-models)
  - [Preparing the Environment](#preparing-the-environment)
  - [(Optional) Building the Container Images](#optional-building-the-container-images)
  - [Installing via Makefile](#installing-via-makefile)
  - [Uninstalling](#uninstalling)
- [Running the Code Understanding Workflow](#running-the-code-understanding-workflow)
- [Running Adhoc Queries](#running-adhoc-queries)
- [Integrating with other tools](#integrating-with-other-tools)
- [More About the Code Understanding Workflow](#more-about-the-code-understanding-workflow)
  - [1. Data Generation](#1-data-generation)
  - [2. Data Indexing](#2-data-indexing)
  - [3. Data Analysis](#3-data-analysis)
- [Add-ons (Optional)](#add-ons)
  - [Code Understanding UI](#code-understanding-ui)
  - [Code Understanding Console Plugin (requires cluster-admin permissions)](#code-understanding-console-plugin)
- [Tags](#tags)

<a id="overview"></a>
## 🧭 Overview

This demonstrates the **Code Understanding** phase of the Agent Mesh for Software Modernization, a framework pattern 
for continuous legacy code which uses a federated, multi-harness, multi-agent 
system (MAS) to support iterative agent-driven development for brownfield applications.

(NOTE: The Agent Mesh consists of two main **workflows**: **Code 
Understanding** and **Code Migration**. This repository demonstrates the **Code Understanding** workflow.)

<a id="tested-with"></a>
## Required Software / Tested with

- Red Hat OpenShift 4.18+ (requires Openshift 4.21+ for UI add-ons)
- Red Hat OpenShift AI 2.22+
- 1X NVIDIA H200 GPU, 1X NVIDIA H100 GPU, 1X NVIDIA L40S GPU
- 8+ vCPUs / 24+ GiB RAM
- A default StorageClass capable of provisioning a 50 GiB ReadWriteOnce PVC for aws-compatible-storage (S4)
- MLflow (assumes Openshift AI 3.4+) [Installation](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/working_with_mlflow/installing-mlflow_mlflow)
- Openshift AI Model Registry [Installation](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/2.25/html-single/enabling_the_model_registry_component/index)
- Openshift AI Model Catalog [Installation](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/working_with_the_model_catalog/index)
- Openshift AI Pipelines [Installation](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/openshift_ai_tutorial_-_fraud_detection_example/setting-up-a-project-and-storage#enabling-ai-pipelines)
- OpenShift CLI (`oc`)
- Helm CLI (`helm`)
- Make (`make`)
- jq (`jq`, for `make verify-deploy`)
- uv CLI (`uv`)
- (**Optional**) Red Hat build of OpenTelemetry operator [Installation](https://docs.redhat.com/en/documentation/openshift_container_platform/4.18/html/distributed_tracing/distributed-tracing-otel-install)
- (**Optional**) Tempo Operator [Installation](https://docs.redhat.com/en/documentation/openshift_container_platform/4.18/html/distributed_tracing/distributed-tracing-tempo-install)

The installer requires permission to manage workloads and resources in the
target project. By default, `make install` also creates the target namespace
and applies the OpenShift AI dashboard label and requester annotation. If an
administrator pre-creates and configures the namespace, run
`make install MANAGE_NAMESPACE=false` to skip those cluster-scoped namespace
operations. The target namespace must already exist and have the
`opendatahub.io/dashboard: "true"` label. If OpenTelemetry is enabled in a
separate namespace, that namespace must also be pre-created.

Workbench ImageStreams are created in the target project and need permission
to manage resources there. Optional OpenTelemetry deployment and the OpenShift
console plugin have additional cluster-scoped requirements; use cluster-admin
or equivalent delegated permissions for those features.

<a id="documentation"></a>

## Installing the Code Understanding Workflow

### Integrating the Models
Ensure that you have access to OpenAI-compatible endpoints for the following models:

| # | Role | Model | Additional Instructions | Links |
|---|------|-------|------------------------|-------|
| 1 | GraphRAG "chat" model | gpt-oss-120b | [Deploying gpt-oss-120b](resources/models/deploying-gpt-oss-120b.md) | <a href="https://microsoft.github.io/graphrag/config/yaml" target="_blank">GraphRAG Docs</a> |
| 2 | GraphRAG "embedding" model | e5-mistral-7b-instruct | [Deploying e5-mistral-7b-instruct](resources/models/deploying-e5-mistral-7b-instruct.md) | <a href="https://microsoft.github.io/graphrag/config/yaml" target="_blank">GraphRAG Docs</a> |
| 3 | Coding agent** | **(Option A)** Gemma-4-31B-it | [Deploying Gemma-4-31B-it](resources/models/deploying-gemma-4-31b.md) | N/A |
| 4 | Coding agent** | **(Option B)** gpt-oss-120b | [Deploying gpt-oss-120b](resources/models/deploying-gpt-oss-120b.md) | N/A |

<sub>**Optional: Used for "Integrating with other tools" (below)</sub>

### Preparing the Environment

1. Create an environment variables file `.env` using `.env.template` as a guide.

   At minimum, configure the following installation and model values:

   - aws-compatible-storage (S4-backed) and project: `AWS_SECRET_ACCESS_KEY` and
     `KFP_NAMESPACE`. `AWS_ACCESS_KEY_ID` defaults to `aws_storage_userid` for the
     bundled S4 service; `AWS_S3_BUCKET` defaults to `data`.
   - GraphRAG chat model: `GRAPHRAG_LLM_TOKEN`, `GRAPHRAG_LLM_ID`,
     `GRAPHRAG_LLM_API_BASE`, `GRAPHRAG_LLM_PROVIDER`, and
     `GRAPHRAG_LLM_PROVIDER_SETTINGS_XML`.
   - GraphRAG embedding model: `EMBED_LLM_TOKEN`, `EMBED_LLM_API_BASE`,
     `EMBED_LLM_ID`, `EMBED_LLM_PROVIDER`, and
     `EMBED_LLM_PROVIDER_SETTINGS_XML`.

   The embedding model values can be omitted when installing the bundled local
   model with `make install DEPLOY_EMBEDDING_MODEL=true`. Git credentials are
   only required when the source or analyzed repositories require
   authentication. Ground-truth, judge, and code model settings are optional
   unless their corresponding evaluation or coding-agent features are used.

### (Optional) Building the Container Images
1. To build the container images, run the following: `make build-images`

### Installing via Makefile
1. Run the Makefile: `make install`
(**NOTE**: To deploy the local `e5-mistral` embedding model as part of installation, run:
   `make install DEPLOY_EMBEDDING_MODEL=true`)

OpenTelemetry and Tempo are optional and disabled by default. To deploy them as
part of installation, run `make install DEPLOY_OTEL=true`.

### Uninstalling

Run:

```sh
make uninstall
```

Uninstall stops project upload/run/query Jobs, removes Kubeflow pipeline
Workflows and their task pods, removes the optional `e5-mistral` release,
uninstalls `agent-mesh-for-sw`, removes the project workbench ImageStreams,
manually created secrets, and operator-generated storage, and deletes the
application's PVC-backed data. The application and OpenTelemetry namespaces are
preserved. OpenTelemetry variables are not required when telemetry was not
deployed.

The uninstall target supports deployments created with the current Helm
ownership model. It does not remove externally stored MLflow data, externally
pushed container images, or the optional cluster-wide OpenShift console plugin.

## Running the Code Understanding Workflow

1. To run the **Code Understanding** pipeline for a single repository, run:

   ```sh
   make run-pipelines ARGS="--single-repo"
   ```

   To override the default repository or branch:
    - Update `GIT_REPO` and `GIT_BRANCH` in `.env` to the desired repository and branch.
    - Run the following: 
   ```sh
   make apply-secrets
   make run-pipelines ARGS="--single-repo"
   ```

   OR without modifying `.env`:
   ```sh
   make run-pipelines ARGS="--single-repo" PIPELINE_GIT_REPO=https://github.com/org/repo PIPELINE_GIT_BRANCH=main
   ```

2. To run the **Code Understanding** pipeline for multiple repositories:
    - Update `workflows/examples/code_understanding/assets/repos/repo_list.json` with the list of repositories to be processed.
    - Run the following command:
   ```sh
   make run-pipelines ARGS="--multi-repo"
   ```

## Running Adhoc Queries
1. To run adhoc queries about the indexed code, run the following:
```wrappers/adhoc.sh <query>```
   - For example: 
     - `wrappers/adhoc.sh "What migration order would be recommended when refactoring to reduce breaking changes?."`
     - `wrappers/adhoc.sh "Which modules or components would be riskiest to refactor first?" --git-repo https://github.com/org/repo` 
     - `wrappers/adhoc.sh "What are the data stores in this codebase?" --git-repo https://github.com/org/repo --git-branch develop`

## Integrating with other tools

External tools — such as vulnerability scanners, dependency analysers, 
static code parsers, etc. — can contribute metadata to the data-generation 
workflow by writing their output as JSON file(s) into a `.code_metadata` directory at the 
root of the repository being analysed. Any files present there are automatically picked up and merged into the generated dataset before indexing. 
Each JSON file must conform to the code metadata schema at [`workflows/examples/code_understanding/assets/schemas/code_metadata_schema.json`](workflows/examples/code_understanding/assets/schemas/code_metadata_schema.json); 
fields not relevant to a given tool can be omitted.

## More About the Code Understanding Workflow

![High Level Overview](code_understanding.jpg)

The **Code Understanding** workflow is the initial **iteration** in the AI 
software modernization process. It is a **tool-driven workflow** which generates artifacts for the 
**refactoring catalog**. These artifacts are optionally combined with 
other tools (organizational vulnerability scanners, static rules engines, 
etc) to build the **migration plan** for the **Code Migration** workflow.

There are three main sub-workflows in the **Code Understanding** workflow:

#### 1. Data Generation

The **Data Generation** sub-workflow is used to generate metadata that will be 
used for GraphRAG-based indexing. For each relevant file in the original 
codebase, it will generate a `.txt` version of the file and a new metadata 
file. This enriched fileset will then be passed as input to the **Data Indexing** workbench in the next step.

#### 2. Data Indexing

The **Data Indexing** sub-workflow is used to index the fileset from the 
**Data Generation** step using GraphRAG. It will generate a graph-based 
representation of the codebase that can be used for querying.

#### 3. Data Analysis

The **Data Analysis** sub-workflow is used to query the generated GraphRAG index using the GraphRAG SDK.
It includes both canned and adhoc queries that can be used to explore the
code and generate assets for the refactoring catalog, including a migration plan.

<a id="add-ons"></a>
## Add-ons (Optional)

Console add-ons use prebuilt images from `KFP_IMAGE_REGISTRY`. Before deploying
either add-on, set `CONSOLE_IMAGE_TAG` in `.env` to the same tag used to build
and push the console images; for the manual GitHub Actions image workflow, this
is the `version` input.

<a id="code-understanding-ui"></a>
### Code Understanding Console App

The Code Understanding Console App is a standalone web interface for managing and running the Code Understanding workflow. 

To deploy the app to your Openshift cluster:
```
make deploy-console-app
# https://code-understanding-console-<namespace>.apps.<cluster-domain>
```

To run the app locally:
```
make run-console-app
# or: ./wrappers/console.sh
# http://127.0.0.1:8080
```

OR port-forward the cluster deployment:

```
make port-forward-console-app
# http://localhost:8080
```

<a id="code-understanding-console-plugin"></a>
### Code Understanding Console Plugin (requires cluster-admin permissions)

The Code Understanding Console Plugin is an OpenShift web-console dynamic 
plugin backed by a FastAPI service. 

Deploy the console plugin:

```
make deploy-console-plugin
```

Then launch:

- **Application launcher** (grid menu, top right) → **Code Understanding**
- Direct URL: `https://<openshift-console-host>/code-understanding`

Navigation also appears under **Administrator** → **Home** → **Code Understanding**. 

**NOTE**: The plugin is enabled cluster-wide through `consoles.operator.openshift.io/cluster`. If it does not appear at first, run `make enable-console-plugin`.

## Tags

- **Title:** Agent Mesh for Software Engineering - Code Understanding
- **Description:** Analyze legacy code with GraphRAG and generate an evidence-based modernization plan on Red Hat OpenShift AI.
- **Industry:** Cross-industry
- **Product:** Red Hat OpenShift AI
- **Use case:** Application modernization, code understanding, generative AI
- **Contributor organization:** Red Hat

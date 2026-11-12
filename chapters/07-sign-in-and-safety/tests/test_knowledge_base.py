"""Chapter 4: the new template parts -- policy folder, vector store, knowledge base and its role."""

from __future__ import annotations

from pathlib import Path

import pytest

CHAPTER = Path(__file__).resolve().parents[1]
# The template sits at the chapter root in the exported repo, and under student/ in the source tree.
TEMPLATES = [CHAPTER / "template.yaml", CHAPTER.parent / "student" / "template.yaml"]


def template_text() -> str:
    template = next((p for p in TEMPLATES if p.is_file()), None)
    if template is None:
        pytest.skip("template.yaml is not beside this folder")
    return template.read_text(encoding="utf-8")


def test_vectors_live_in_an_s3_vector_index_that_matches_the_embedding_model() -> None:
    text = template_text()
    assert "Type: AWS::S3Vectors::VectorBucket" in text
    assert "Type: AWS::S3Vectors::Index" in text
    assert "Type: S3_VECTORS" in text
    assert "amazon.titan-embed-text-v2:0" in text
    assert "Dimension: 1024" in text  # the default output size of that embedding model
    assert "DataType: float32" in text


def test_index_keeps_the_text_and_metadata_the_knowledge_base_writes_non_filterable() -> None:
    text = template_text()
    assert "AMAZON_BEDROCK_TEXT" in text and "AMAZON_BEDROCK_METADATA" in text


def test_knowledge_base_reads_only_the_policy_folder() -> None:
    text = template_text()
    assert "InclusionPrefixes" in text and "policies/" in text
    assert "Type: S3" in text
    assert "DataDeletionPolicy: DELETE" in text  # so the vector bucket is empty when the stack goes


def test_knowledge_base_role_is_scoped_to_this_account_and_knowledge_bases() -> None:
    text = template_text()
    assert "bedrock.amazonaws.com" in text
    assert "aws:SourceAccount" in text
    assert "s3vectors:QueryVectors" in text and "s3vectors:PutVectors" in text


def test_function_may_query_the_knowledge_base_and_is_wired_to_it() -> None:
    text = template_text()
    assert "bedrock:RetrieveAndGenerate" in text
    assert "bedrock:Retrieve" in text
    assert "KNOWLEDGE_BASE_ID" in text and "MODEL_ARN" in text


def test_nothing_is_retained_on_delete() -> None:
    assert "Retain" not in template_text()


def test_template_names_resources_from_project_and_environment() -> None:
    text = template_text()
    assert '!Sub "${Project}-${Environment}-ask"' in text
    assert '!Sub "${Project}-${Environment}-api"' in text
    assert '!Sub "${Project}-${Environment}-policies"' in text
    assert '!Sub "${Project}-${Environment}-policy-pages"' in text
    assert "${AWS::StackName}" not in text


def test_template_lets_the_role_call_an_inference_profile() -> None:
    # Most Regions serve the model only through an inference profile (geo prefix + model id);
    # the role must allow the profile and the model in every Region the profile routes to.
    text = template_text()
    assert ":inference-profile/${Id}" in text
    assert "bedrock:*::foundation-model/${ModelId}" in text
    assert "ap-south-1: {Route: apac}" in text


def test_model_arn_can_be_an_inference_profile_arn() -> None:
    # retrieve_and_generate takes the model as an ARN; in most Regions that must be the profile's.
    text = template_text()
    start = text.index("MODEL_ARN: !If")
    arn = text[start : text.index("LoggingConfig:", start)]
    assert "CallsInferenceProfile" in arn
    assert ":inference-profile/${Id}" in arn
    assert "::foundation-model/${ModelId}" in arn  # the direct route keeps the model ARN


def test_template_keeps_nothing_after_delete() -> None:
    # DataDeletionPolicy (the data source's DELETE) is a different setting and is checked above.
    text = template_text().replace("DataDeletionPolicy", "")
    assert "DeletionPolicy" not in text and "UpdateReplacePolicy" not in text

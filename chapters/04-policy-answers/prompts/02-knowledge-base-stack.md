# 02 - The vector store and the knowledge base

## Goal

Add the vector storage, the knowledge base that fills it from the policy folder, and the roles that let each part do only its job.

## Prompt

```text
Extend template.yaml (chapter 3's stack). Change the chapter tag on every resource that supports
tags to session-04, keeping its project and environment tags, and keep every chapter 3 resource
and logical id. Keep the Project, Environment, ModelId and ModelRoute parameters, and name the
new resources ${Project}-${Environment}-<part>, never from the stack name.

- PolicyVectorBucket (AWS::S3Vectors::VectorBucket) and PolicyVectorIndex (AWS::S3Vectors::Index)
  in it: data type float32, dimension 1024, distance metric cosine, and the non-filterable
  metadata keys AMAZON_BEDROCK_TEXT and AMAZON_BEDROCK_METADATA. Tag both with chapter: session-04,
  project and environment.
- KnowledgeBaseRole (IAM): bedrock.amazonaws.com may assume it only for this account
  (aws:SourceAccount) and only for knowledge bases in this Region. It may invoke the Titan Text
  Embeddings V2 model (amazon.titan-embed-text-v2:0), list the site bucket, read objects under
  policies/ in it (both limited to this account with aws:ResourceAccount), and use the vector
  index (s3vectors PutVectors, GetVectors, DeleteVectors, QueryVectors, GetIndex).
- PolicyKnowledgeBase (AWS::Bedrock::KnowledgeBase): type VECTOR, that embedding model, storage
  type S3_VECTORS with the index ARN, the role above, named ${Project}-${Environment}-policies,
  tags chapter: session-04, project and environment.
- PolicyDataSource (AWS::Bedrock::DataSource): named ${Project}-${Environment}-policy-pages, type S3, the site bucket, inclusion prefix
  policies/, and DataDeletionPolicy DELETE so the vectors are removed with it.
- The function role may call bedrock:RetrieveAndGenerate and bedrock:Retrieve on this knowledge
  base (keep its other permissions, including bedrock:InvokeModel on the chosen model: for a
  profile route, the profile in this Region plus the foundation model in every Region; for a
  direct route, the foundation model in this Region). The function gets environment variables
  KNOWLEDGE_BASE_ID and MODEL_ARN (the ARN of the inference profile when the route is a profile,
  built from the ModelRoute and ModelId parameters; the foundation model ARN when it is direct);
  MODEL_ID is gone. Add an output ModelInUse, as in chapter 2.
- Outputs KnowledgeBaseId and DataSourceId. No Retain deletion policy anywhere.

Then create tests/test_knowledge_base.py, which only reads the template (skip if it is not beside
the folder) and checks: the vector bucket, index, S3_VECTORS storage, embedding model id and
dimension 1024; the two non-filterable keys; the policies/ prefix and the delete policy; the role's
account condition and s3vectors actions; the function's permissions and environment variables; that MODEL_ARN can be an inference profile
ARN; that resource names come from Project and Environment, never the stack name; that the role
allows an inference profile and the model in every Region; and that nothing is retained.
```

## Check

```bash
pytest -q tests/test_knowledge_base.py
cfn-lint template.yaml
grep -n "S3_VECTORS\|DataDeletionPolicy\|InclusionPrefixes" template.yaml
```

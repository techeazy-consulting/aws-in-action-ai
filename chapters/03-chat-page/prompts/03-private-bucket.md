# 03 - A private bucket and an origin access control

## Goal

Add a bucket nobody can read directly, and the CloudFront setting that lets only your distribution read it.

## Prompt

```text
Extend template.yaml (chapter 2's stack) with these resources, and change the chapter tag on every
resource that supports tags to session-03, keeping its project and environment tags. Keep every
chapter 2 resource, its logical id, the Project, Environment, ModelId and ModelRoute parameters
and the role's model permission.

- SiteBucket, an AWS::S3::Bucket: ownership controls BucketOwnerEnforced, all four Block Public
  Access settings true, default encryption AES256, tag chapter: session-03. No website
  configuration and no retention policy.
- SiteOriginAccessControl, an AWS::CloudFront::OriginAccessControl: origin type s3, signing
  behavior always, signing protocol sigv4, a name built as Project-Environment-site, never from the stack name. Tag the bucket with
  project and environment too.
```

## Check

```bash
cfn-lint template.yaml
grep -n "BlockPublicAcls\|SigningBehavior" template.yaml
```

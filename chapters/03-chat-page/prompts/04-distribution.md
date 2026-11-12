# 04 - One address for the page and /ask

## Goal

Put CloudFront in front of the bucket and the API so the page and its endpoint share one HTTPS address.

## Prompt

```text
Extend template.yaml with a CloudFront distribution and a bucket policy.

- SiteDistribution, an AWS::CloudFront::Distribution: enabled, HTTP/2, price class 100, default
  root object index.html, tag chapter: session-03. It uses the default CloudFront domain, which
  CloudFront serves over HTTPS.
- Two origins. "site": the bucket's regional domain name, with the origin access control id and an
  empty origin access identity. "api": the HTTP API's host name built from the API id and the
  region pseudo parameter, with HTTPS only and TLS 1.2.
- Default behavior to "site": redirect HTTP to HTTPS, GET and HEAD only, the managed CachingOptimized
  cache policy (658327ea-f89d-4fab-a63d-7e88639e58f6).
- A behavior for path /ask to "api": redirect HTTP to HTTPS, all HTTP methods allowed, the managed
  CachingDisabled cache policy (4135ea2d-6df8-44a3-9df3-4b5a84be39ad) and the managed
  AllViewerExceptHostHeader origin request policy (b689b0a8-53d0-40ab-baf2-68738e2966ac), because
  the API expects its own host name.
- SiteBucketPolicy, an AWS::S3::BucketPolicy: allow the service principal cloudfront.amazonaws.com
  to s3:GetObject on the bucket's objects, only when AWS:SourceArn equals this distribution's ARN
  (partition, account id and distribution id from pseudo parameters and a reference).
- Outputs ChatUrl (the distribution's domain name as an HTTPS address) and SiteBucketName.
```

## Check

```bash
cfn-lint template.yaml
grep -n "PathPattern\|ViewerProtocolPolicy\|AWS:SourceArn" template.yaml
pytest -q
```

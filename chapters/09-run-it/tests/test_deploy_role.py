"""Chapter 8: the bootstrap template -- the GitHub provider and the two roles. Read as data."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
import yaml

CHAPTER = Path(__file__).resolve().parents[1]
# The file sits at the chapter root in the exported repo, and under student/ in the source tree.
CANDIDATES = [CHAPTER / "deploy-role.yaml", CHAPTER.parent / "student" / "deploy-role.yaml"]


class Loader(yaml.SafeLoader):
    """Reads CloudFormation short-form tags (!Ref, !Sub) as plain data."""


def _intrinsic(loader: Loader, suffix: str, node: yaml.Node) -> dict[str, Any]:
    key = suffix if suffix == "Ref" else f"Fn::{suffix}"
    if isinstance(node, yaml.ScalarNode):
        return {key: loader.construct_scalar(node)}
    if isinstance(node, yaml.SequenceNode):
        return {key: loader.construct_sequence(node, deep=True)}
    assert isinstance(node, yaml.MappingNode)
    return {key: loader.construct_mapping(node, deep=True)}


Loader.add_multi_constructor("!", _intrinsic)


def path() -> Path:
    found = next((p for p in CANDIDATES if p.is_file()), None)
    if found is None:
        pytest.skip("deploy-role.yaml is not beside this folder")
    return found


def template() -> dict[str, Any]:
    loaded = yaml.load(path().read_text(encoding="utf-8"), Loader=Loader)  # noqa: S506
    assert isinstance(loaded, dict)
    return loaded


def resources() -> dict[str, Any]:
    return template()["Resources"]


def statements(role: str) -> list[dict[str, Any]]:
    policy = resources()[role]["Properties"]["Policies"][0]["PolicyDocument"]
    return policy["Statement"]


def test_the_github_provider_is_the_documented_url_and_audience() -> None:
    provider = resources()["GitHubOidcProvider"]
    assert provider["Type"] == "AWS::IAM::OIDCProvider"
    scheme = "https:" + "//"  # built, so no learner file carries a literal link
    assert provider["Properties"]["Url"] == scheme + "token.actions.githubusercontent.com"
    assert provider["Properties"]["ClientIdList"] == ["sts.amazonaws.com"]
    assert provider["Condition"] == "MakeProvider"  # one provider per account: optional here


def test_an_account_that_already_has_the_provider_can_pass_its_arn_instead() -> None:
    params = template()["Parameters"]
    assert params["CreateProvider"]["AllowedValues"] == ["true", "false"]
    assert params["ExistingProviderArn"]["Default"] == ""
    assert "oidc-provider/token" in params["ExistingProviderArn"]["AllowedPattern"]
    principal = resources()["GitHubDeployRole"]["Properties"]["AssumeRolePolicyDocument"]["Statement"][0]["Principal"]
    assert principal == {
        "Federated": {"Fn::If": ["MakeProvider", {"Ref": "GitHubOidcProvider"}, {"Ref": "ExistingProviderArn"}]}
    }


def test_the_subject_prefix_has_no_default_and_no_wildcard() -> None:
    prefix = template()["Parameters"]["GitHubSubjectPrefix"]
    assert "Default" not in prefix
    pattern = re.compile(prefix["AllowedPattern"])
    assert pattern.fullmatch("repo:octo-org/octo-repo")
    assert pattern.fullmatch("repo:octo-org@123456/octo-repo@456789")  # the numeric-id format
    for bad in ("repo:octo-org/*", "repo:*", "repo:octo-org/octo-repo:*", "repo:octo-org", "octo-org/octo-repo",
                "repo:octo-org/octo-repo:environment:prod", "repo:a b/c", "repo:a/b\\nrepo:c/d"):
        assert not pattern.fullmatch(bad), bad


def test_only_a_job_in_the_staging_or_prod_environment_of_this_repository_can_assume_the_role() -> None:
    trust = resources()["GitHubDeployRole"]["Properties"]["AssumeRolePolicyDocument"]["Statement"][0]
    assert trust["Action"] == "sts:AssumeRoleWithWebIdentity"
    assert trust["Effect"] == "Allow"
    assert set(trust["Condition"]) == {"StringEquals"}  # exact match: no StringLike, no wildcard
    equals = trust["Condition"]["StringEquals"]
    assert equals["token.actions.githubusercontent.com:aud"] == "sts.amazonaws.com"
    assert equals["token.actions.githubusercontent.com:sub"] == [
        {"Fn::Sub": "${GitHubSubjectPrefix}:environment:staging"},
        {"Fn::Sub": "${GitHubSubjectPrefix}:environment:prod"},
    ]
    assert "*" not in path().read_text(encoding="utf-8").split("AssumeRolePolicyDocument")[2].split("Policies")[0]


def main_template() -> dict[str, Any]:
    candidates = [CHAPTER / "template.yaml", CHAPTER.parent / "student" / "template.yaml"]
    found = next((p for p in candidates if p.is_file()), None)
    if found is None:
        pytest.skip("template.yaml is not beside this folder")
    loaded = yaml.load(found.read_text(encoding="utf-8"), Loader=Loader)  # noqa: S506
    assert isinstance(loaded, dict)
    return loaded


def actions_of(statement: dict[str, Any]) -> list[str]:
    action = statement["Action"]
    return action if isinstance(action, list) else [action]


def test_the_deploy_role_can_run_cloudformation_on_helpdesk_stacks_and_nothing_else_broad() -> None:
    by_id = {s["Sid"]: s for s in statements("GitHubDeployRole")}
    stacks = by_id["RunCloudFormationOnHelpdeskStacksOnly"]
    assert stacks["Resource"] == {
        "Fn::Sub": "arn:${AWS::Partition}:cloudformation:${AWS::Region}:${AWS::AccountId}:stack/helpdesk-*/*"
    }
    assert "cloudformation:DeleteStack" not in stacks["Action"]  # a workflow cannot delete a stack
    for statement in by_id.values():
        for action in statement["Action"] if isinstance(statement["Action"], list) else [statement["Action"]]:
            assert not action.endswith(":*") and action != "*", action
    assert by_id["ReadATemplateSummary"]["Resource"] == "*"  # the one action with no resource form


def test_the_deploy_role_may_pass_only_the_cloudformation_role_and_only_to_cloudformation() -> None:
    statement = next(s for s in statements("GitHubDeployRole") if s["Action"] == "iam:PassRole")
    assert statement["Resource"] == {"Fn::GetAtt": "CloudFormationExecutionRole.Arn"}
    assert statement["Condition"] == {"StringEquals": {"iam:PassedToService": "cloudformation.amazonaws.com"}}


def test_the_deploy_role_may_put_pages_only_in_helpdesk_site_buckets_of_this_account() -> None:
    statement = next(s for s in statements("GitHubDeployRole") if s["Sid"] == "PublishThePagesToTheSiteBuckets")
    assert sorted(statement["Action"]) == ["s3:ListBucket", "s3:PutObject"]  # no read, no delete
    for resource in statement["Resource"]:
        assert "helpdesk-*-site-${AWS::AccountId}-${AWS::Region}" in resource["Fn::Sub"]


def test_only_cloudformation_can_assume_the_execution_role() -> None:
    trust = resources()["CloudFormationExecutionRole"]["Properties"]["AssumeRolePolicyDocument"]["Statement"]
    assert trust == [
        {"Effect": "Allow", "Principal": {"Service": "cloudformation.amazonaws.com"}, "Action": "sts:AssumeRole"}
    ]


def test_no_account_id_key_email_or_brand_is_written_in_the_file() -> None:
    text = path().read_text(encoding="utf-8")
    assert not re.search(r"(?<!\d)\d{12}(?!\d)", text)
    assert not re.search(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b", text)
    assert not re.search(r"[A-Za-z0-9._-]+@[A-Za-z0-9-]+\.[A-Za-z]{2,}", text)


EXEC = "CloudFormationExecutionRole"


def test_a_role_can_be_created_or_changed_only_with_the_boundary_attached() -> None:
    stmt = next(x for x in statements(EXEC) if x["Sid"] == "CreateAndChangeRolesOnlyWithTheBoundary")
    assert {"iam:CreateRole", "iam:PutRolePolicy", "iam:UpdateAssumeRolePolicy", "iam:DeleteRolePolicy"} == set(actions_of(stmt))
    assert stmt["Condition"] == {"StringEquals": {"iam:PermissionsBoundary": {"Ref": "HelpdeskPermissionsBoundary"}}}
    assert stmt["Resource"] == {"Fn::Sub": "arn:${AWS::Partition}:iam::${AWS::AccountId}:role/helpdesk-*"}


def test_every_iam_action_of_the_execution_role_is_on_helpdesk_roles_only() -> None:
    iam = [x for x in statements(EXEC) if any(a.startswith("iam:") for a in actions_of(x))]
    assert {x["Sid"] for x in iam} == {
        "CreateAndChangeRolesOnlyWithTheBoundary",
        "ReadTagAndDeleteHelpdeskRoles",
        "PassHelpdeskRolesToLambdaAndBedrockOnly",
    }
    for stmt in iam:
        assert stmt["Resource"] == {"Fn::Sub": "arn:${AWS::Partition}:iam::${AWS::AccountId}:role/helpdesk-*"}
        assert all(a.startswith("iam:") for a in actions_of(stmt))


def test_the_execution_role_cannot_attach_policies_or_touch_a_boundary() -> None:
    every = {a for x in statements(EXEC) for a in actions_of(x)}
    forbidden = {
        "iam:*", "iam:AttachRolePolicy", "iam:DetachRolePolicy", "iam:PutRolePermissionsBoundary",
        "iam:DeleteRolePermissionsBoundary", "iam:CreatePolicy", "iam:CreatePolicyVersion",
        "iam:SetDefaultPolicyVersion", "iam:DeletePolicy", "iam:CreateUser", "iam:CreateAccessKey",
        "iam:PutUserPolicy", "iam:AttachUserPolicy", "iam:CreateLoginProfile", "sts:*",
    }
    assert not (every & forbidden), every & forbidden


def test_roles_are_passed_only_to_lambda_and_bedrock() -> None:
    stmt = next(x for x in statements(EXEC) if x["Sid"] == "PassHelpdeskRolesToLambdaAndBedrockOnly")
    assert stmt["Action"] == "iam:PassRole"
    assert stmt["Condition"] == {
        "StringEquals": {"iam:PassedToService": ["lambda.amazonaws.com", "bedrock.amazonaws.com"]}
    }


def test_the_bootstrap_roles_are_named_outside_the_pattern_the_execution_role_manages() -> None:
    for role in (EXEC, "GitHubDeployRole"):
        name = resources()[role]["Properties"]["RoleName"]["Fn::Sub"]
        assert not name.startswith("helpdesk-"), f"{role} is named inside the pattern it must not manage"


def boundary_statements() -> list[dict[str, Any]]:
    policy = resources()["HelpdeskPermissionsBoundary"]
    assert policy["Type"] == "AWS::IAM::ManagedPolicy"
    return policy["Properties"]["PolicyDocument"]["Statement"]


def test_the_boundary_names_exact_actions_and_never_a_wildcard() -> None:
    for stmt in boundary_statements():
        assert stmt["Effect"] == "Allow"
        for action in actions_of(stmt):
            assert "*" not in action, action
    assert not any(a.startswith("iam:") or a.startswith("sts:") for x in boundary_statements() for a in actions_of(x))


def test_the_boundary_covers_every_action_the_helpdesks_own_roles_use_and_adds_nothing_unused() -> None:
    used: set[str] = set()
    roles = [r for r in main_template()["Resources"].values() if r["Type"] == "AWS::IAM::Role"]
    assert len(roles) >= 5
    for role in roles:
        for policy in role["Properties"].get("Policies", []):
            for stmt in policy["PolicyDocument"]["Statement"]:
                used |= set(actions_of(stmt))
    allowed = {a for x in boundary_statements() for a in actions_of(x)}
    assert used <= allowed, used - allowed  # a role would lose a permission it needs
    assert allowed <= used, allowed - used  # the ceiling is no higher than the roles need


def test_the_boundary_is_an_output_and_the_deploy_role_cannot_edit_it() -> None:
    assert set(template()["Outputs"]) == {"DeployRoleArn", "CloudFormationRoleArn", "PermissionsBoundaryArn"}
    role_level = {
        "iam:CreateRole", "iam:DeleteRole", "iam:DeleteRolePolicy", "iam:GetRole", "iam:GetRolePolicy",
        "iam:ListAttachedRolePolicies", "iam:ListRolePolicies", "iam:PassRole", "iam:PutRolePolicy",
        "iam:TagRole", "iam:UntagRole", "iam:UpdateAssumeRolePolicy",
    }
    every = {a for role in (EXEC, "GitHubDeployRole") for x in statements(role) for a in actions_of(x)}
    assert {a for a in every if a.startswith("iam:")} <= role_level  # no policy or boundary action at all


def test_only_aud_and_sub_are_used_as_trust_conditions_because_aws_offers_no_other_github_key() -> None:
    trust = resources()["GitHubDeployRole"]["Properties"]["AssumeRolePolicyDocument"]["Statement"][0]
    keys = set(trust["Condition"]["StringEquals"])
    assert keys == {"token.actions.githubusercontent.com:aud", "token.actions.githubusercontent.com:sub"}


def test_every_taggable_resource_is_tagged_with_the_chapter_and_nothing_is_retained() -> None:
    for name, resource in resources().items():
        if resource["Type"] == "AWS::IAM::ManagedPolicy":  # this type has no Tags property
            continue
        assert {"Key": "chapter", "Value": "session-09"} in resource["Properties"]["Tags"], name
        assert "DeletionPolicy" not in resource and "UpdateReplacePolicy" not in resource


def deploy_by_id() -> dict[str, dict[str, Any]]:
    return {x["Sid"]: x for x in statements("GitHubDeployRole")}


def test_the_quality_check_may_invoke_only_the_ask_function_of_a_helpdesk_stack() -> None:
    stmt = deploy_by_id()["InvokeTheAskFunctionForTheQualityCheck"]
    assert stmt["Action"] == "lambda:InvokeFunction"
    assert stmt["Resource"]["Fn::Sub"].endswith(":function:helpdesk-*-ask")


def test_the_deploy_role_can_start_and_watch_an_ingestion_job_and_do_nothing_else_in_bedrock() -> None:
    stmt = deploy_by_id()["RunAndWatchAnIngestionJob"]
    assert sorted(stmt["Action"]) == ["bedrock:GetIngestionJob", "bedrock:StartIngestionJob"]
    assert stmt["Resource"]["Fn::Sub"].endswith(":knowledge-base/*")


def test_alarms_dashboards_and_metric_filters_are_limited_to_helpdesk_names() -> None:
    by_id = {x["Sid"]: x for x in statements("CloudFormationExecutionRole")}
    assert by_id["HelpdeskAlarms"]["Resource"]["Fn::Sub"].endswith(":alarm:helpdesk-*")
    assert by_id["HelpdeskDashboards"]["Resource"]["Fn::Sub"].endswith(":dashboard/helpdesk-*")
    assert by_id["HelpdeskMetricFilters"]["Resource"]["Fn::Sub"].endswith("log-group:/aws/lambda/helpdesk-*:*")
    for sid in ("HelpdeskAlarms", "HelpdeskDashboards", "HelpdeskMetricFilters"):
        assert not any(a.endswith(":*") for a in actions_of(by_id[sid])), sid
    listing = by_id["ListAlarms"]
    assert listing["Action"] == "cloudwatch:DescribeAlarms" and listing["Resource"] == "*"


CHAPTER_TAG = "session-09"
# Tag keys a create or tag call may set: the chapter tag, plus the stack tags CloudFormation adds.
TAG_KEYS = {"ForAllValues:StringLike": {"aws:TagKeys": ["chapter", "project", "environment", "aws:cloudformation:*"]}}
TAGGED = {"StringEquals": {"aws:RequestTag/chapter": CHAPTER_TAG}, **TAG_KEYS}
TAG_TESTED = {"StringEquals": {"aws:ResourceTag/chapter": CHAPTER_TAG}}


def exec_by_id() -> dict[str, dict[str, Any]]:
    return {x["Sid"]: x for x in statements("CloudFormationExecutionRole")}


def resource_list(stmt: dict[str, Any]) -> list[Any]:
    value = stmt["Resource"]
    return value if isinstance(value, list) else [value]


def test_no_action_of_the_cloudformation_role_is_a_service_wildcard() -> None:
    for stmt in statements("CloudFormationExecutionRole"):
        for action in actions_of(stmt):
            assert "*" not in action, f"{stmt['Sid']}: {action}"


def test_resource_is_everything_only_where_the_service_gives_no_narrower_form() -> None:
    allowed = {
        "ListLogGroupsAndFilters": None,  # describe actions take no resource
        "ListAlarms": None,
        "CreateTaggedBedrockResources": TAGGED,  # creating has no resource to name: the tag is the limit
        "CreateTaggedDistributionsAndUserPools": TAGGED,
        "CreateAnOriginAccessControl": None,  # an access control can be neither tagged nor tag-tested
    }
    star = {x["Sid"] for x in statements("CloudFormationExecutionRole") if x["Resource"] == "*"}
    star -= {"ListLogGroups"}  # chapter 8 name of the logs listing
    assert star <= set(allowed), star - set(allowed)
    by_id = exec_by_id()
    for sid, condition in allowed.items():
        if sid in by_id and condition is not None:
            assert by_id[sid].get("Condition") == condition, sid
    assert by_id["CreateAnOriginAccessControl"]["Action"] == "cloudfront:CreateOriginAccessControl"


def test_functions_logs_tables_topics_and_buckets_are_limited_to_helpdesk_names() -> None:
    by_id = exec_by_id()
    assert by_id["HelpdeskFunctions"]["Resource"]["Fn::Sub"].endswith(":function:helpdesk-*")
    assert by_id["HelpdeskLogGroups"]["Resource"]["Fn::Sub"].endswith("log-group:/aws/lambda/helpdesk-*")
    assert by_id["HelpdeskTopics"]["Resource"]["Fn::Sub"].endswith(":helpdesk-*")
    assert by_id["HelpdeskTables"]["Resource"]["Fn::Sub"].endswith(":table/helpdesk-*")
    bucket = by_id["TheSiteBucketsOnly"]["Resource"]["Fn::Sub"]
    assert bucket.endswith("helpdesk-*-site-${AWS::AccountId}-${AWS::Region}")  # the bucket, not its objects
    assert not any(a in {"s3:GetObject", "s3:PutObject", "s3:DeleteObject"} for a in actions_of(by_id["TheSiteBucketsOnly"]))


def test_api_gateway_is_limited_to_http_apis_and_their_tags_in_this_region() -> None:
    stmt = exec_by_id()["HttpApisInThisRegion"]
    assert sorted(actions_of(stmt)) == ["apigateway:DELETE", "apigateway:GET", "apigateway:PATCH", "apigateway:POST", "apigateway:PUT"]
    paths = ["/" + r["Fn::Sub"].rsplit("::/", 1)[1] for r in resource_list(stmt)]
    assert paths == ["/apis", "/apis/*", "/tags/*"]
    assert all("${AWS::Region}" in r["Fn::Sub"] for r in resource_list(stmt))


@pytest.mark.parametrize(
    "sid, actions",
    [
        ("CreateTaggedBedrockResources", {"bedrock:CreateGuardrail", "bedrock:CreateKnowledgeBase"}),
        ("CreateTaggedDistributionsAndUserPools", {"cloudfront:CreateDistribution", "cognito-idp:CreateUserPool"}),
        ("CreateTaggedVectorBucketsAndIndexes", {"s3vectors:CreateIndex", "s3vectors:CreateVectorBucket"}),
    ],
)
def test_creating_these_needs_the_chapter_tag_on_the_request(sid: str, actions: set[str]) -> None:
    stmt = exec_by_id()[sid]
    assert set(actions_of(stmt)) == actions and stmt["Condition"] == TAGGED


@pytest.mark.parametrize(
    "sid, actions",
    [
        ("TagDistributionsAndUserPools", {"cloudfront:TagResource", "cognito-idp:TagResource"}),
        ("TagBedrockResourcesWithTheChapterTag", {"bedrock:TagResource"}),
        ("TagTaggedVectorBucketsAndIndexes", {"s3vectors:TagResource"}),
    ],
)
def test_tagging_after_creation_needs_the_chapter_tag_already_on_the_resource(sid: str, actions: set[str]) -> None:
    # Without the resource-tag test, the role could stamp the chapter tag onto any untagged
    # resource in the account and then manage it.
    stmt = exec_by_id()[sid]
    assert set(actions_of(stmt)) == actions
    assert stmt["Condition"] == {
        "StringEquals": {"aws:RequestTag/chapter": CHAPTER_TAG, "aws:ResourceTag/chapter": CHAPTER_TAG},
        **TAG_KEYS,
    }


@pytest.mark.parametrize(
    "sid",
    ["ManageTaggedDistributions", "ManageTaggedUserPools", "ManageTaggedVectorBucketsAndIndexes", "ManageBedrockResourcesInThisAccountAndRegion"],
)
def test_everything_after_creation_is_limited_to_resources_that_carry_the_chapter_tag(sid: str) -> None:
    stmt = exec_by_id()[sid]
    assert stmt["Condition"] == TAG_TESTED
    assert not any(a.split(":")[1].startswith(("Create", "Tag")) for a in actions_of(stmt) if a.split(":")[1] not in {"CreateGroup", "CreateUserPoolClient", "CreateDataSource", "CreateGuardrailVersion"}), sid


def test_cognito_and_cloudfront_resources_are_limited_to_this_account_and_region() -> None:
    by_id = exec_by_id()
    assert "${AWS::AccountId}:userpool/*" in by_id["ManageTaggedUserPools"]["Resource"]["Fn::Sub"]
    assert "${AWS::Region}" in by_id["ManageTaggedUserPools"]["Resource"]["Fn::Sub"]
    assert "cloudfront::${AWS::AccountId}:distribution/*" in by_id["ManageTaggedDistributions"]["Resource"]["Fn::Sub"]
    oac = by_id["ManageOriginAccessControlsInThisAccount"]
    assert oac["Resource"]["Fn::Sub"].endswith("cloudfront::${AWS::AccountId}:origin-access-control/*")


def test_bedrock_and_vector_bucket_management_stays_in_this_account_and_region() -> None:
    by_id = exec_by_id()
    for sid in ("ManageBedrockResourcesInThisAccountAndRegion", "TagBedrockResourcesWithTheChapterTag"):
        for r in resource_list(by_id[sid]):
            assert "${AWS::Region}:${AWS::AccountId}:" in r["Fn::Sub"], sid
    assert "${AWS::Region}:${AWS::AccountId}:bucket/*" in by_id["ManageTaggedVectorBucketsAndIndexes"]["Resource"]["Fn::Sub"]


def test_the_template_tags_every_cloudfront_cognito_bedrock_and_vector_resource_the_conditions_test() -> None:
    text = main_text()
    for logical in ("SiteDistribution", "HelpdeskUserPool", "HelpdeskGuardrail", "PolicyKnowledgeBase", "PolicyVectorBucket", "PolicyVectorIndex"):
        block = text.split(f"\n  {logical}:\n")[1].split("\n\n  ")[0]
        assert "chapter" in block and "session-0" in block, logical


def main_text() -> str:
    candidates = [CHAPTER / "template.yaml", CHAPTER.parent / "student" / "template.yaml"]
    found = next((p for p in candidates if p.is_file()), None)
    if found is None:
        pytest.skip("template.yaml is not beside this folder")
    return found.read_text(encoding="utf-8")


def test_the_boundary_lets_a_model_be_called_through_an_inference_profile() -> None:
    # The profile is in this Region and routes to the model in any Region in its geography.
    stmt = next(x for x in boundary_statements() if x["Sid"] == "CallModelsAndTheGuardrail")
    resources_ = [r["Fn::Sub"] for r in stmt["Resource"]]
    assert "arn:${AWS::Partition}:bedrock:*::foundation-model/*" in resources_
    assert "arn:${AWS::Partition}:bedrock:${AWS::Region}:${AWS::AccountId}:inference-profile/*" in resources_

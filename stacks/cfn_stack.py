from aws_cdk import(
    aws_s3 as s3,
    aws_cloudfront as cdn,
    aws_ssm as ssm,
    aws_s3_deployment as s3_deploy,
    aws_route53 as r53,
    aws_route53_targets as r53targets,
    aws_elasticloadbalancingv2 as elbv2,
    aws_wafv2 as wafv2,
    core
)
from cloudcomponents.cdk_lambda_at_edge_pattern import HttpHeaders

import json
import jsii

# this is needed to fix a bug in CDK
@jsii.implements(wafv2.CfnRuleGroup.IPSetReferenceStatementProperty)
class IPSetReferenceStatement:
    @property
    def arn(self):
        return self._arn

    @arn.setter
    def arn(self, value):
        self._arn = value

class CFNStack(core.Stack):

    def __init__(self, scope: core.Construct, id: str, acmcert, env, alb=elbv2.ApplicationLoadBalancer, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        domain_name = env['domain_name']
        env_name    = env['env']
        restricted_countries = env['restricted_countries']

        zone_id = ssm.StringParameter.from_string_parameter_name(self, 'zone-id-ssm', string_parameter_name='/'+env_name+'/zone-id')

         
        ##############################################################################
        # Create S3 static Website
        ##############################################################################

        account_id = core.Aws.ACCOUNT_ID

        FrontendBucket = s3.Bucket(self, 'FrontendWebsite',
            encryption=s3.BucketEncryption.S3_MANAGED,
            bucket_name=account_id+'-'+env_name+'-frontend',
            website_index_document="index.html",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL
        )

        s3_deploy.BucketDeployment(self, "DeployFrontendWebsite",
            sources=[s3_deploy.Source.asset("./static-content")],
            destination_bucket=FrontendBucket,
        )

        origin_access_identity = cdn.OriginAccessIdentity(
            self, "OriginAccessIdentity",
            comment="Allows Read-Access from CloudFront"
        )

        FrontendBucket.grant_read(origin_access_identity)

        ##############################################################################
        # Create the WAF regex pattern and IP sets
        ##############################################################################

        ip_set_v4 = wafv2.CfnIPSet(
            self,
            "IPSetv4",
            addresses=[
                "1.2.3.4/32",
                "5.6.7.8/32",
            ],
            ip_address_version="IPV4",
            scope="CLOUDFRONT",
        )
        #note we use the class declared above to get around a bug in CDK
        ip_ref_statement_v4 = IPSetReferenceStatement()
        ip_ref_statement_v4.arn = ip_set_v4.attr_arn

        regex_pattern_set = wafv2.CfnRegexPatternSet(
            self,
            "RegexPatternSet",
            regular_expression_list=["^.*(Mozilla).*$"],
            scope="CLOUDFRONT",
            description="Checks user-agent for signatures that match devices",
            name="device-detector",
        )

        regex_statement = (
            wafv2.CfnWebACL.RegexPatternSetReferenceStatementProperty(
                arn=regex_pattern_set.attr_arn,
                field_to_match=wafv2.CfnWebACL.FieldToMatchProperty(
                    single_header={"Name": "User-Agent"}
                ),
                text_transformations=[
                    wafv2.CfnWebACL.TextTransformationProperty(priority=0, type="NONE")
                ],
            )
        )
        
        ##############################################################################
        # Create WAF
        ##############################################################################

        waf = wafv2.CfnWebACL(
            self,
            "CloudFrontWebACL",
            ####################################################################################
            # Set this to allow|block to enable/prevent access to requests not matching a rule
            ####################################################################################
            default_action=wafv2.CfnWebACL.DefaultActionProperty(allow={}),
            scope="CLOUDFRONT",
            visibility_config=wafv2.CfnWebACL.VisibilityConfigProperty(
                cloud_watch_metrics_enabled=True,
                metric_name="WAF",
                sampled_requests_enabled=True,
            ),
            rules=[
                #blocks any user agents NOT matching the regex
                wafv2.CfnWebACL.RuleProperty(
                    name="Permitted-User-Agents",
                    priority=0,
                    action=wafv2.CfnWebACL.RuleActionProperty(block={}),
                    visibility_config=wafv2.CfnWebACL.VisibilityConfigProperty(
                        sampled_requests_enabled=True,
                        cloud_watch_metrics_enabled=True,
                        metric_name="allow-permitted-devices",
                    ),
                    statement=wafv2.CfnWebACL.StatementProperty(
                        not_statement=wafv2.CfnWebACL.NotStatementProperty(
                            statement=wafv2.CfnWebACL.StatementProperty(
                                regex_pattern_set_reference_statement=regex_statement
                            )
                        )
                    ),
                ),
                wafv2.CfnWebACL.RuleProperty(
                    name="Permitted-IPs",
                    priority=1,
                    action=wafv2.CfnWebACL.RuleActionProperty(block={}),
                    visibility_config=wafv2.CfnWebACL.VisibilityConfigProperty(
                        sampled_requests_enabled=True,
                        cloud_watch_metrics_enabled=True,
                        metric_name="allow-permitted-ips",
                    ),
                    statement=wafv2.CfnWebACL.StatementProperty(
                        ip_set_reference_statement=ip_ref_statement_v4
                    ),
                ),
                wafv2.CfnWebACL.RuleProperty(
                    name="AWS-AWSManagedRulesCommonRuleSet",
                    priority=3,
                    statement=wafv2.CfnWebACL.StatementProperty(
                        managed_rule_group_statement=wafv2.CfnWebACL.ManagedRuleGroupStatementProperty(
                            vendor_name="AWS", name="AWSManagedRulesCommonRuleSet"
                        )
                    ),
                    override_action=wafv2.CfnWebACL.OverrideActionProperty(none={}),
                    visibility_config=wafv2.CfnWebACL.VisibilityConfigProperty(
                        sampled_requests_enabled=True,
                        cloud_watch_metrics_enabled=True,
                        metric_name="AWS-AWSManagedRulesCommonRuleSet",
                    ),
                ),
            ],
        )

        ##############################################################################
        # Create Cloudfront
        ##############################################################################

        http_headers = HttpHeaders(self, "HttpHeaders",
            http_headers={
                "Content-Security-Policy": "default-src 'self'; img-src 'self'; script-src 'self' https://bencap.de; style-src 'self' 'unsafe-inline' https://bencap.de ; object-src 'none'; connect-src 'self'  https://*.amazonaws.com https://*.amazoncognito.com ",
                #"Content-Security-Policy-Report-Only": "default-src 'none'; img-src 'self'; script-src 'self'; style-src 'self'; object-src 'none'; connect-src 'self' https://*.amazonaws.com https://*.amazoncognito.com",
                "Strict-Transport-Security": "max-age=31536000; includeSubdomains; preload",
                "Referrer-Policy": "same-origin",
                "X-XSS-Protection": "1; mode=block",
                "X-Frame-Options": "DENY",
                "X-Content-Type-Options": "nosniff",
                "Cache-Control": "no-cache"
            }
        )
        
        self.cdn_id = cdn.CloudFrontWebDistribution(self,'webhosting-cdn',
            web_acl_id=waf.attr_arn,
            geo_restriction=cdn.GeoRestriction.denylist(restricted_countries),
            origin_configs=[
                cdn.SourceConfiguration(
                    #origin_path="/",
                    s3_origin_source=cdn.S3OriginConfig(
                        s3_bucket_source=FrontendBucket,
                        origin_access_identity=origin_access_identity
                    ),
                    behaviors=[
                        cdn.Behavior(
                            is_default_behavior=True,
                            allowed_methods= cdn.CloudFrontAllowedMethods.GET_HEAD,
                            cached_methods= cdn.CloudFrontAllowedCachedMethods.GET_HEAD,
                            viewer_protocol_policy=cdn.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                            lambda_function_associations= [http_headers],
                        )
                    ],
                ),
                cdn.SourceConfiguration(
                    custom_origin_source=cdn.CustomOriginConfig(
                        domain_name=alb.load_balancer_dns_name,
                        origin_protocol_policy= cdn.OriginProtocolPolicy.HTTP_ONLY,
                ),
                    behaviors = [ 
                        cdn.Behavior(
                            path_pattern="/api",
                            allowed_methods= cdn.CloudFrontAllowedMethods.GET_HEAD,
                            viewer_protocol_policy=cdn.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                            forwarded_values= {
                                "query_string":True,
                                "cookies": {"forward": "all"},
                                "headers": ['*']
                            },
                        )
                    ]   
                )
            ],

            error_configurations=[cdn.CfnDistribution.CustomErrorResponseProperty(
                error_code=400,
                response_code=200,
                response_page_path="/"

            ),
                cdn.CfnDistribution.CustomErrorResponseProperty(
                    error_code=403,
                    response_code=200,
                    response_page_path="/"
                ),
                cdn.CfnDistribution.CustomErrorResponseProperty(
                    error_code=404,
                    response_code=200,
                    response_page_path="/"
                )
            ],
            alias_configuration=cdn.AliasConfiguration(
                acm_cert_ref=acmcert.certificate_arn,
                names=[domain_name,'www.'+domain_name]
            ),
            logging_config= ({}),
        )

        ssm.StringParameter(self,'cdn-dist-id',
            parameter_name='/'+env_name+'/app-distribution-id',
            string_value=self.cdn_id.distribution_id
        )

        ssm.StringParameter(self,'cdn-url',
            parameter_name='/'+env_name+'/app-cdn-url',
            string_value='https://'+self.cdn_id.domain_name
        )

        # Add DNS record for Cloudfront 
        dns_zone = r53.HostedZone.from_hosted_zone_attributes(self, 'hosted-zone',
            hosted_zone_id=zone_id.string_value,
            zone_name=domain_name
        )

        r53.ARecord(self, 'website-record',
            zone=dns_zone,
            target=r53.RecordTarget.from_alias(alias_target=r53targets.CloudFrontTarget(self.cdn_id)),
        )

        dns_www_zone = r53.HostedZone.from_hosted_zone_attributes(self, 'hosted-zone-www',
            hosted_zone_id=zone_id.string_value,
            zone_name='www.'+domain_name
        )

        r53.ARecord(self, 'website-www-record',
            zone=dns_www_zone,
            target=r53.RecordTarget.from_alias(alias_target=r53targets.CloudFrontTarget(self.cdn_id)),
        )
from aws_cdk import(
    aws_route53 as r53,
    aws_ssm as ssm,
    core
)

class DNSStack(core.Stack):

    def __init__(self, scope: core.Construct, id: str, env, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        domain_name = env['domain_name']
        env_name    = env['env']

        self.hosted_zone =r53.HostedZone(self, 'hosted-zone',
            zone_name= domain_name
        )

        ssm.StringParameter(self,'zone-id',
            parameter_name='/'+env_name+'/zone-id',
            string_value=self.hosted_zone.hosted_zone_id
        )
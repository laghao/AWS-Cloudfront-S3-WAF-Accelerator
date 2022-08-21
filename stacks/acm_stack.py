from aws_cdk import (
    aws_certificatemanager as acm,
    aws_route53 as r53,
    aws_ssm as ssm,
    core
) 

class ACMStack(core.Stack):

    def __init__(self, scope: core.Construct, id: str, env,  **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        domain_name = env['domain_name']
        env_name    = env['env']
        aws_region  = env['aws_region']

        zone_id = ssm.StringParameter.from_string_parameter_name(self, 'zone-id-ssm', string_parameter_name='/'+env_name+'/zone-id')

        dns_zone = r53.HostedZone.from_hosted_zone_attributes(self, 'hosted-zone',
            hosted_zone_id=zone_id.string_value,
            zone_name=domain_name
        )

        self.cert_manager = acm.DnsValidatedCertificate(self, 'acm-us-east-1',
            hosted_zone=dns_zone,
            domain_name=domain_name,
            subject_alternative_names=['*.'+domain_name,domain_name],
            region= aws_region
        )

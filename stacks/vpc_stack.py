from aws_cdk import(
    aws_ec2 as ec2,
    aws_iam as iam,
    aws_ssm as ssm,
    aws_logs as logs,
    aws_accessanalyzer as accessanalyzer,
    core
)

class VPCStack(core.Stack):

    def __init__(self, scope: core.Construct, id: str, env, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)
        
        domain_name = env['domain_name']
        env_name    = env['env']
        prj_name    = env['project_name']

        # VPC Flow logs requirements setup
        vpc_flow_role = iam.Role(
            self, 'FlowLog',
            assumed_by=iam.ServicePrincipal('vpc-flow-logs.amazonaws.com')
        )

        log_group = logs.LogGroup(
            self, 'LogGroup',
            log_group_name=prj_name,
            retention=logs.RetentionDays('ONE_YEAR'),
            removal_policy=core.RemovalPolicy('DESTROY')
            )

        # VPC Configuration
        self.vpc = ec2.Vpc(self, 'devVPC',
            cidr="10.0.0.0/16",
            max_azs=2,
            enable_dns_hostnames=True,
            enable_dns_support=True,
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="Public",
                    subnet_type=ec2.SubnetType.PUBLIC,
                    cidr_mask=24
                ),
                ec2.SubnetConfiguration(
                    name="Private",
                    subnet_type=ec2.SubnetType.PRIVATE,
                    cidr_mask=24
                ),
                ec2.SubnetConfiguration(
                    name="Isolated",
                    subnet_type=ec2.SubnetType.ISOLATED,
                    cidr_mask=24
                ),
            ],
        )

        # VPC Flow logs configuration
        vpc_log = ec2.CfnFlowLog(
            self, 'FlowLogs',
            resource_id=self.vpc.vpc_id,
            resource_type='VPC',
            traffic_type='ALL',
            deliver_logs_permission_arn=vpc_flow_role.role_arn,
            log_destination_type='cloud-watch-logs',
            log_group_name=log_group.log_group_name
        )

        # SSM Parameters for subnets
        priv_subnets = [subnet.subnet_id for subnet in self.vpc.private_subnets]

        count = 1
        for ps in priv_subnets:
            ssm.StringParameter(self, 'private-subnet-'+str(count),
                string_value=ps,
                parameter_name='/'+env_name+'/private_subnet-'+str(count)
            )
            count += 1

        cfn_analyzer = accessanalyzer.CfnAnalyzer(self, "MyCfnAnalyzer",
            type="ACCOUNT",
            analyzer_name=prj_name+'NetworkAnalyzer',
        )   
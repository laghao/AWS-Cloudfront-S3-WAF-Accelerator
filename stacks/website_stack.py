from aws_cdk import (
    core,
    aws_ec2 as ec2,
    aws_elasticloadbalancingv2 as elbv2,
)


class WebsiteStack(core.Stack):

    def __init__(self, scope: core.Construct, id: str, vpc:ec2.Vpc, env, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        with open("./user-data/user_data.sh") as f:
            user_data = f.read()

        self.sg_www = ec2.SecurityGroup(
            self,
            'www',
            vpc=vpc,
            description="Allow WWW from anywhere",
            security_group_name="WWW from anywhere"
        )

        linux_ami = ec2.GenericLinuxImage({
            "us-east-1": "ami-02e136e904f3da870",
            "us-west-1": "ami-03ab7423a204da002"
        })

        host = ec2.Instance(
            self,
            'website',
            instance_type=ec2.InstanceType('t2.micro'),
            machine_image=linux_ami,
            vpc=vpc,
            security_group=self.sg_www,
            user_data=ec2.UserData.custom(user_data),
        )

        tg = elbv2.ApplicationTargetGroup(
            self,
            'website-target-group',
            protocol=elbv2.ApplicationProtocol.HTTP,
            port=80,
            target_type=elbv2.TargetType.INSTANCE,

            vpc=vpc,

            health_check=elbv2.HealthCheck(
                healthy_http_codes='200',
                path='/api'
            ),
        )

        tg.add_target(elbv2.InstanceTarget(host.instance_id, port=80))

        self.lb = elbv2.ApplicationLoadBalancer(
            self,
            'website-load-balancer',
            vpc=vpc,
            internet_facing=True,
            security_group=self.sg_www,
        )
        listener = self.lb.add_listener("website-listener", port=80)
        listener.add_target_groups("http", target_groups=[tg])

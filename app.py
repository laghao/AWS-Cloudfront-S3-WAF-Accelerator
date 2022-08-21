#!/usr/bin/env python3
import os
import yaml

from aws_cdk import core
from stacks.vpc_stack import VPCStack
from stacks.website_stack import WebsiteStack
from stacks.dns_stack import DNSStack
from stacks.cfn_stack import CFNStack
from stacks.acm_stack import ACMStack

env = yaml.load(open("environment.yml"), Loader=yaml.FullLoader)

config_dict = {
    'project_name': f"{os.environ.get('PROJECT', env['project_name'])}",
    'env': f"{os.environ.get('ENVIRONMENT', env['env'])}",
    'vpc_name': f"{os.environ.get('VPCNAME', env['vpc_name'])}",
    'domain_name': os.environ.get("DOMAIN_NAME", env['domain_name']),
    'aws_region': os.environ.get("AWS_DEFAULT_REGION", env['aws_region']),
    'restricted_countries': os.environ.get("restricted_countries", env['restricted_countries'])
    }

app = core.App()

vpc_stack               = VPCStack(app, 'vpc-stack', env=config_dict)
website_stack           = WebsiteStack(app, 'website-stack', vpc=vpc_stack.vpc, env=config_dict)
website_stack.add_dependency(vpc_stack)
dns_stack               = DNSStack(app, 'dns-stack', env=config_dict)
dns_stack.add_dependency(website_stack)
acm_stack               = ACMStack(app, 'acm-stack', env=config_dict)
acm_stack.add_dependency(dns_stack)
cfn_stack               = CFNStack(app, 'cfn-stack',alb=website_stack.lb, acmcert=acm_stack.cert_manager, env=config_dict)
cfn_stack.add_dependency(acm_stack)

app.synth()

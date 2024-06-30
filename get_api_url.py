#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import argparse
import os
import json


def parse_args(raw_args):
    parser = argparse.ArgumentParser()
    dirname = os.path.dirname(os.path.realpath(__file__))

    parser.add_argument("-t", "--tf_state",
                        default=f"{dirname}/open-tofu/terraform.tfstate")
    return parser.parse_args(raw_args)

# Main function. Optional raw_args array for specifying command line arguments in calls from other python scripts. If raw_args=none, argparse will get the arguments from the command line.
def main(raw_args=None):
    # Get the arguments object.
    args = parse_args(raw_args)

    # Load the tf state file.
    with open(args.tf_state) as stream:

        tfstate = json.load(stream)
        resources = tfstate['resources']
        for resource in resources:
            resource_type = resource['type']
            if resource_type == "aws_api_gateway_deployment":
                instance = resource['instances'][0]
                print(instance['attributes']['invoke_url'])




# Invoke this script after provisioning via open-tofu to print the API's url.

# Main module init for direct invocation. 
if __name__ == '__main__':
    main()
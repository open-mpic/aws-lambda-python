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


def extract_api_key(raw_args=None):
    args = parse_args(raw_args)  # get the arguments object
    with open(args.tf_state) as stream:  # load the tf state file
        tfstate = json.load(stream)
        resources = tfstate['resources']
        for resource in resources:
            resource_type = resource['type']
            if resource_type == "aws_api_gateway_api_key":
                instance = resource['instances'][0]
                return instance['attributes']['value']


# Main function. Optional raw_args array for specifying command line arguments in calls from other python scripts. If raw_args=none, argparse will get the arguments from the command line.
def main(raw_args=None):
    print(extract_api_key(raw_args))


# Invoke this script after provisioning via open-tofu to print the API's url.

# Main module init for direct invocation. 
if __name__ == '__main__':
    main()

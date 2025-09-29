#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import argparse
import json
import os
from typing import Dict

import yaml
import secrets
import string


def parse_args(raw_args):
    parser = argparse.ArgumentParser()
    dirname = os.path.dirname(os.path.realpath(__file__))

    parser.add_argument("-c", "--config",
                        default=f"{dirname}/config.yaml")
    parser.add_argument("-r", "--available_regions",
                        default=f"{dirname}/aws-available-regions.yaml")
    parser.add_argument("-m", "--main_tf_template",
                        default=f"{dirname}/open-tofu/main.tf.template")
    parser.add_argument("-a", "--aws_perspective_tf_template",
                        default=f"{dirname}/open-tofu/aws-perspective.tf.template")
    parser.add_argument("-p", "--aws_provider_tf_template",
                        default=f"{dirname}/open-tofu/aws-provider.tf.template")
    parser.add_argument("-d", "--deployment_id_file",
                        default=f"{dirname}/deployment.id")
    return parser.parse_args(raw_args)


# Main function. Optional raw_args array for specifying command line arguments in calls from other python scripts. If raw_args=none, argparse will get the arguments from the command line.
def main(raw_args=None):
    # Get the arguments object.
    args = parse_args(raw_args)

    # If the deployment id file does not exist, make a new one.
    if not os.path.isfile(args.deployment_id_file):
        with open(args.deployment_id_file, 'w') as stream:
            deployment_id_to_write = ''.join(secrets.choice(string.digits) for _ in range(10))
            stream.write(deployment_id_to_write)
    
    # Read the deployment id.
    with open(args.deployment_id_file) as stream:
        deployment_id = int(stream.read())

    # Load the config.
    config = {}
    with open(args.config) as stream:
        try:
            config = yaml.safe_load(stream)
        except yaml.YAMLError as exc:
            print(f"Error loading YAML config at {args.config}. Project not configured. Error details: {exc}.")
            exit()
    aws_available_regions = {}
    with open(args.available_regions) as stream:
        try:
            aws_available_regions = yaml.safe_load(stream)['aws-available-regions']
        except yaml.YAMLError as exc:
            print(f"Error loading YAML config at {args.available_regions}. Project not configured. Error details: {exc}.")
            exit()

    # Remove all old files.
    open_tofu_dir = '/'.join(args.aws_perspective_tf_template.split('/')[:-1])
    for file in os.listdir(open_tofu_dir):
        if file.endswith(".generated.tf"):
            os.remove(os.path.join(open_tofu_dir, file))

    # Generate "main.generated.tf" based on main.tf.template.
    with open(args.main_tf_template) as stream:
        perspective_config: Dict[str, dict] = {}
        region_codes = config['perspectives']

        # Read the template file to a string.
        main_tf_string = stream.read()

        # Replace all the template vars used in the file.
        main_tf_string = main_tf_string.replace("{{api-region}}", config['api-region'])
        main_tf_string = main_tf_string.replace("{{deployment-id}}", str(deployment_id))

        # Construct the perspective configuration.
        for region_code in region_codes:
            perspective_endpoints = {
                'caa_endpoint_info': {
                    'arn': f"${{aws_lambda_function.mpic_caa_checker_lambda_{region_code}.arn}}"
                },
                'dcv_endpoint_info': {
                    'arn': f"${{aws_lambda_function.mpic_dcv_checker_lambda_{region_code}.arn}}"
                }
            }
            perspective_config[region_code] = perspective_endpoints

        perspective_config_as_json = json.dumps(perspective_config, ensure_ascii=False)
        main_tf_string = main_tf_string.replace("{{perspectives}}", perspective_config_as_json)

        # Replace default perspective count.
        main_tf_string = main_tf_string.replace("{{default-perspective-count}}", f"\"{config['default-perspective-count']}\"")

        # Replace absolute max attempt count if present.
        if "absolute-max-attempts" in config:
            main_tf_string = main_tf_string.replace("{{absolute-max-attempts-with-key}}", f"absolute_max_attempts = \"{config['absolute-max-attempts']}\"")
        else:
            main_tf_string = main_tf_string.replace("{{absolute-max-attempts-with-key}}", "")

        # Store the secret key for the vantage points hash in an environment variable.
        hash_secret = ''.join(secrets.choice(string.ascii_letters) for _ in range(20))
        main_tf_string = main_tf_string.replace("{{hash-secret}}", f"\"{hash_secret}\"")
        
        # Set the source path for the lambda functions.
        main_tf_string = main_tf_string.replace("{{source-path}}", f"{config['source-path']}")

        main_tf_string = set_common_env_configuration(main_tf_string, config)

        # Derive the out file from the input file name.
        if not args.main_tf_template.endswith(".tf.template"):
            print(f"Error: invalid tf template name: {args.main_tf_template}. Make sure all tf template files end in '.tf.template'.")
            exit()
        
        out_file_name = f"{'.'.join(args.main_tf_template.split('.')[:-2])}.generated.tf"

        with open(out_file_name, 'w') as out_stream:
            out_stream.write(main_tf_string)

    with open(args.aws_provider_tf_template) as stream:
        aws_provider_tf = stream.read()
        result_string = ""
        for region in aws_available_regions:
            result_string += aws_provider_tf.replace("{{region}}", region)
            result_string += "\n"
        out_file_name = f"{'.'.join(args.aws_provider_tf_template.split('.')[:-2])}.generated.tf"

        with open(out_file_name, 'w') as out_stream:
            out_stream.write(result_string)

    # Generate aws-perspective-template.generated.tf based on aws-perspective-template.tf.template.
    with open(args.aws_perspective_tf_template) as stream:
        # Read the template file to a string.
        aws_perspective_tf = stream.read()

        # Iterate through the different regions specified and produce an output file for each region.
        for region in config['perspectives']:
            aws_perspective_tf_region = aws_perspective_tf.replace("{{region}}", region)

            # Construct the default CAA domain list.
            default_caa_domains_list = "|".join(config['caa-domains'])
            aws_perspective_tf_region = aws_perspective_tf_region.replace("{{default-caa-domains}}", f"\"{default_caa_domains_list}\"")

            # Set the source path for the lambda functions.
            aws_perspective_tf_region = aws_perspective_tf_region.replace("{{source-path}}", f"{config['source-path']}")

            aws_perspective_tf_region = set_common_env_configuration(aws_perspective_tf_region, config)

            if not args.aws_perspective_tf_template.endswith(".tf.template"):
                print(f"Error: invalid tf template name: {args.aws_perspective_tf_template}. Make sure all tf template files end in '.tf.template'.")
                exit()
            out_file_name = f"{'.'.join(args.aws_perspective_tf_template.split('.')[:-2])}.{region}.generated.tf"

            with open(out_file_name, 'w') as out_stream:
                out_stream.write(aws_perspective_tf_region)
        

def set_common_env_configuration(tf_string: str, config: dict) -> str:
    # set log level if present
    if "log-level" in config:
        tf_string = tf_string.replace("{{log-level-with-key}}", f"log_level = \"{config['log-level']}\"")
    else:
        tf_string = tf_string.replace("{{log-level-with-key}}", "")

    # set timeouts if present
    if "http-client-timeout-seconds" in config:
        tf_string = tf_string.replace("{{http-client-timeout-with-key}}", f"http_client_timeout_seconds = {config['http-client-timeout-seconds']}")
    else:
        tf_string = tf_string.replace("{{http-client-timeout-with-key}}", "")
    if "dns-timeout-seconds" in config:
        tf_string = tf_string.replace("{{dns-timeout-with-key}}", f"dns_timeout_seconds = {config['dns-timeout-seconds']}")
    else:
        tf_string = tf_string.replace("{{dns-timeout-with-key}}", "")
    if "dns-resolution-lifetime-seconds" in config:
        tf_string = tf_string.replace("{{dns-resolution-lifetime-with-key}}", f"dns_resolution_lifetime_seconds = {config['dns-resolution-lifetime-seconds']}")
    else:
        tf_string = tf_string.replace("{{dns-resolution-lifetime-with-key}}", "")

    return tf_string


# Main module init for direct invocation. 
if __name__ == '__main__':
    main()

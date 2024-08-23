#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import argparse
import os
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
            deployment_id_to_write = ''.join(secrets.choice(string.digits) for i in range(10))
            stream.write(deployment_id_to_write)
    
    # Read the deployment id.
    deployment_id = 0
    with open(args.deployment_id_file) as stream:
        deployment_id = int(stream.read())

    # Load the config.
    config = {}
    with open(args.config) as stream:
        try:
            config = yaml.safe_load(stream)
        except yaml.YAMLError as exc:
            print(f"Error loading YAML config at {args.config}. Project not configured. Error details: {exec}.")
            exit()
    aws_available_regions = {}
    with open(args.available_regions) as stream:
        try:
            aws_available_regions = yaml.safe_load(stream)['aws-available-regions']
        except yaml.YAMLError as exc:
            print(f"Error loading YAML config at {args.available_regions}. Project not configured. Error details: {exec}.")
            exit()

    # Remove all old files.
    open_tofu_dir = '/'.join(args.aws_perspective_tf_template.split('/')[:-1])
    for file in os.listdir(open_tofu_dir):
        if file.endswith(".generated.tf"):
            os.remove(os.path.join(open_tofu_dir, file))

    regions = [perspective.split('.')[1] for perspective in config['perspectives']] 

    # Generate "main.generated.tf" based on main.tf.template.
    with open(args.main_tf_template) as stream:
        # Read the template file to a string.
        main_tf_string = stream.read()

        # Replace all the template vars used in the file.
        main_tf_string = main_tf_string.replace("{{api-region}}", config['api-region'])
        main_tf_string = main_tf_string.replace("{{deployment-id}}", str(deployment_id))
        
        # Generate the region name list.
        perspective_names_list = "|".join(config['perspectives'])
        # Note the substitution uses quotes around the var.
        main_tf_string = main_tf_string.replace("{{perspective-names-list}}", f"\"{perspective_names_list}\"")
        
        # Generate the ARNs list for validators. Note that this is not a list of actual ARN values. It is just a list of ARN names that will be substituted by Open Tofu.
        arn_validator_list = "|".join([f"${{aws_lambda_function.lambda_validator_{region}.arn}}" for region in regions])
        main_tf_string = main_tf_string.replace("{{validator-arns-list}}", f"\"{arn_validator_list}\"")
        
        # Generate the ARNs list for CAA resolvers. Note that this is not a list of actual ARN values. It is just a list of ARN names that will be substituted by Open Tofu.
        arn_mpic_caa_checker_list = "|".join([f"${{aws_lambda_function.mpic_caa_checker_lambda_{region}.arn}}" for region in regions])
        main_tf_string = main_tf_string.replace("{{mpic-caa-checker-arns-list}}", f"\"{arn_mpic_caa_checker_list}\"")

        # Replace default perspective count.
        main_tf_string = main_tf_string.replace("{{default-perspective-count}}", f"\"{config['default-perspective-count']}\"")

        # Replace enforce distinct rir regions.
        main_tf_string = main_tf_string.replace("{{enforce-distinct-rir-regions}}", f"\"{1 if config['enforce-distinct-rir-regions'] else 0}\"")

        # Store the secret key for the vantage points hash in an environment variable.
        hash_secret = ''.join(secrets.choice(string.ascii_letters) for i in range(20))
        main_tf_string = main_tf_string.replace("{{hash-secret}}", f"\"{hash_secret}\"")
        
        # Set the source path for the lambda functions.
        main_tf_string = main_tf_string.replace("{{source-path}}", f"{config['source-path']}")

        # Derive the out file from the input file name.
        if not args.main_tf_template.endswith(".tf.template"):
            print(f"Error: invalid tf template name: {args.main_tf_template}. Make sure all tf tempalte files end in '.tf.template'.")
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
        for region in regions:
            aws_perspective_tf_region = aws_perspective_tf.replace("{{region}}", region)
            
            # Replace the deployment id.
            aws_perspective_tf_region = aws_perspective_tf_region.replace("{{deployment-id}}", str(deployment_id))
            # Construct the default CAA domain list.
            default_caa_domains_list = "|".join(config['caa-domains'])
            aws_perspective_tf_region = aws_perspective_tf_region.replace("{{default-caa-domains}}", f"\"{default_caa_domains_list}\"")

            # Set the source path for the lambda functions.
            aws_perspective_tf_region = aws_perspective_tf_region.replace("{{source-path}}", f"{config['source-path']}")

            if not args.aws_perspective_tf_template.endswith(".tf.template"):
                print(f"Error: invalid tf template name: {args.aws_perspective_tf_template}. Make sure all tf template files end in '.tf.template'.")
                exit()
            out_file_name = f"{'.'.join(args.aws_perspective_tf_template.split('.')[:-2])}.{region}.generated.tf"

            with open(out_file_name, 'w') as out_stream:
                out_stream.write(aws_perspective_tf_region)
        

# Main module init for direct invocation. 
if __name__ == '__main__':
    main()
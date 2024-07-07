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
    parser.add_argument("-m", "--main_tf_template",
                        default=f"{dirname}/open-tofu/main.tf.template")
    parser.add_argument("-a", "--aws_perspective_tf_template",
                        default=f"{dirname}/open-tofu/aws-perspective.tf.template")
    return parser.parse_args(raw_args)

# Main function. Optional raw_args array for specifying command line arguments in calls from other python scripts. If raw_args=none, argparse will get the arguments from the command line.
def main(raw_args=None):
    # Get the arguments object.
    args = parse_args(raw_args)

    # Load the config.
    config = {}
    with open(args.config) as stream:
        try:
            config = yaml.safe_load(stream)
        except yaml.YAMLError as exc:
            print(f"Error loading YAML config at {args.config}. Project not configured. Error details: {exec}.")
            exit()


    regions = [perspective.split('.')[1] for perspective in config['perspectives']] 

    # Generate main.generated.tf based on main.tf.template.
    with open(args.main_tf_template) as stream:

        # Read the template file to a string.
        main_tf_string = stream.read()

        # Replace all the template vars used in the file.
        
        main_tf_string = main_tf_string.replace("{{api-region}}", config['api-region'])
        
        # Generate the region name list.
        perspective_names_list = "|".join(config['perspectives'])
        # Note the substitution uses quotes around the var.
        main_tf_string = main_tf_string.replace("{{perspective-names-list}}", f"\"{perspective_names_list}\"")
        
        
        # Generate the ARNs list for validators. Note that this is not a list of actual ARN values. It is just a list of ARN names that will be substituted by Open Tofu.
        arn_validator_list = "|".join([f"${{aws_lambda_function.lambda_validator_{region}.arn}}" for region in regions])
        main_tf_string = main_tf_string.replace("{{validator-arns-list}}", f"\"{arn_validator_list}\"")
        
        # Generate the ARNs list for CAA resolvers. Note that this is not a list of actual ARN values. It is just a list of ARN names that will be substituted by Open Tofu.
        arn_caa_resolver_list = "|".join([f"${{aws_lambda_function.lambda_caa_resolver_{region}.arn}}" for region in regions])
        main_tf_string = main_tf_string.replace("{{caa-resolver-arns-list}}", f"\"{arn_caa_resolver_list}\"")
        

        # Replace default perspective count and default quorum.
        main_tf_string = main_tf_string.replace("{{default-perspective-count}}", f"\"{config['default-perspective-count']}\"")
        main_tf_string = main_tf_string.replace("{{default-quorum}}", f"\"{config['default-quorum']}\"")
        
        # Replace enforce distinct rir regions.
        main_tf_string = main_tf_string.replace("{{enforce-distinct-rir-regions}}", f"\"{1 if config['enforce-distinct-rir-regions'] else 0}\"")
        

        # Store the secret key for the vantage points hash in an environment variable.
        hash_secret = ''.join(secrets.choice(string.ascii_letters) for i in range(20))
        main_tf_string = main_tf_string.replace("{{hash-secret}}", f"\"{hash_secret}\"")
        

        # Derive the out file from the input file name.
        if not args.main_tf_template.endswith(".tf.template"):
            print(f"Error: invalid tf template name: {args.main_tf_template}. Make sure all tf tempalte files end in '.tf.template'.")
            exit()
        
        out_file_name = f"{'.'.join(args.main_tf_template.split('.')[:-2])}.generated.tf"

        with open(out_file_name, 'w') as out_stream:
            out_stream.write(main_tf_string)

    # Generate aws-perspective-template.generated.tf based on aws-perspective-template.tf.template.
    with open(args.aws_perspective_tf_template) as stream:

        # Read the template file to a string.
        aws_perspective_tf = stream.read()

        # Iterate through the different regions specified and produce an output file for each region.
        for region in regions:
            aws_perspective_tf_region = aws_perspective_tf.replace("{{region}}", region)
            
            # Construct the default CAA domain list.
            default_caa_domains_list = "|".join(config['caa-domains'])
            aws_perspective_tf_region = aws_perspective_tf_region.replace("{{default-caa-domains}}", f"\"{default_caa_domains_list}\"")

            if not args.aws_perspective_tf_template.endswith(".tf.template"):
                print(f"Error: invalid tf template name: {args.aws_perspective_tf_template}. Make sure all tf tempalte files end in '.tf.template'.")
                exit()
            out_file_name = f"{'.'.join(args.aws_perspective_tf_template.split('.')[:-2])}.{region}.generated.tf"

            with open(out_file_name, 'w') as out_stream:
                out_stream.write(aws_perspective_tf_region)
        






# Main module init for direct invocation. 
if __name__ == '__main__':
    main()
# aws-lambda-python
An implementation of the Open MPIC API using AWS-Lambda serverless fucntions written in Python as well as AWS API Gateway.

# Deployment
As this API runs serverless in the cloud, it is not installed but rather deployed. The below instructions deploy the API in a user's AWS account and create a unique API endpoint for that user.

## Requirements
All requirements for running the API are packaged and uploaded to AWS as a lambda layer. However, the machine deploying the API must have the following requirements
- The AWS CLI (https://aws.amazon.com/cli/) installed with default profile login credentials. The script currently uses the "default" profile to deploy the API to. If you have multiple AWS profiles, ensure the one you want to use for the API in listed as default in ~/.aws/credentials. You can alternatively change the AWS module parameters in main.tf to use an alternate profile.
- Open Tofu (https://opentofu.org/) is installed. This is an open-source fork of Terraform and the configs in this project are largely interoperable between the two.
- Python3.11 which can be run with the command `python3.11`
- Bash. Several deployment scripts are written for bash.
- A Python3 install linked to the command python3 and the requirements from requirements.txt (in the root directory) installed. These requirements are for the configure.py script (run on the local machine) and are distinct from the requirements in layer/requirements.txt which are requirements for the AWS Lambda Functions run in the cloud.

## Deployment Steps
1. Install layer dependencies. cd to the `layer` directory. Run `./1-install.sh` to create a virtual Python environment and install the project dependencies via pip.
2. Package the AWS layer. In the `layer` directory, run `./2-package.sh`. This will make a file called `layer_content.zip` which will later be referenced by Open Tofu.
3. Zip all functions. AWS Lambda functions are usually deployed from zip files. cd to the main project directory and then run `./zip-all.sh`
4. Edit config.yaml to contain the proper values needed for the deployment. A default config.yaml for a 6-perspective deployment with the controller in us-east-2 is included in this repo.
5. Run `./configure.py` from the root directory of the repo to generate Open Tofu files from templates.
7. Deploy the entire package with Open Tofu. cd to the `open-tofu` directory where .tf files are located. Then run `tofu init`. Then run `tofu apply` and type `yes` at the confirmation prompt.
8. Get the URL of the deployed API endpoint by running `./get_api_url.py` in the root directory.

## Testing
If you log into your AWS account, you can now see the API listed under the AWS API Gateway page. From here you can get the API URL provided by amazon or test the API directly with different parameters. You can also view and test the individual lambda functions that are called.

## Development
Code changes can easily be deployed by editing the .py files and then rezipping the project via `./zip-all.sh`. Then, running `tofu apply` run from the open-tofu directory will update only on the required resources and leave the others unchanged. If any `.tf.template` files are changed or `config.yaml` is edited, `./configure.py` must be rerun followed by `tofu apply` in the open-tofu directory.

`.generated.tf` files should not be edited directly and are not checked into git. Edit `.tf.template` files and regenerate the files via `./configure.py`.

## Tear-down
If you would like to take the API down, run `tofu destroy` in the open-tofu directory and type `yes` at the prompt. This will remove all AWS resources created by Open Tofu for the API.
`./clean.sh` in the root directory also clears generated/zip files.

# Timeline of remaining tasks

The Open MPIC project is currently under development. The pre-alpha release includes support for the HTTP and DNS domain validation methods using Amazon Web Services Lambda and API Gateway. The work items remaining to a feature-complete production-level product include the following: (subject to change)

- API Testing scripts and usage examples. Tentative completion date: 7/25/2024
- Support for additional features in the API specification. Some features in the API specification (like TLS-ALPN support) are not in the current prototype. We plan to make the prototype a complete implementation of the API specification. Tentative completion date: 8/10/2024
- Final testing and debugging. Tentative completion date: 9/1/2024

Throughout the development process, we will address any GitHub issues raised, and may modify the API accordingly. We also welcome pull requests from the general community.

## Completed Tasks
- Automatic provisioning of lambda functions based on a configuration file. This will eliminate the need to create the lambda functions one by one and simply allow a single config file to specify the entire system configuration which is then deployed automatically. completion date: 6/29/2024
- Full conformance to the published [API specification](https://github.com/open-mpic/open-mpic-specification). Because development on the current implementation began as we were standardizing the API specification, there are currently some discrepancies that we plan to resolve. This update will make calls to the lambda API compliant with the specification. completion date: 6/30/2024

## Tasks without assigned timelines
There are several features that may be of interest to the community but we don't yet have a specific completion timeline. These may be given higher priority based on feedback and community interest.

- Support for retrieval of contact information from whois and DNS for the purpose of validation. Several validation methods require contact information to be retrieved via multiple perspectives (e.g., email to domain CAA contact) which is then used in a subsequent validation step (that may not actually require MPIC). The API could support this by allowing a single API call to retrieve the contact info and then perform a set comparison (based on the quorum policy) to return contact info that could be used for validation.
- Support for CAA extensions. CAA issue tags can potentially have extensions to specify things like account ID or validation method per [RFC 8657](https://datatracker.ietf.org/doc/html/rfc8657). The API could potentially take validation method or account id as an optional parameter and perform the processing on these CAA extensions to have them correctly impact the API response.

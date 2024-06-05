# aws-lambda-python
An implementation of the Open MPIC API using AWS-Lambda serverless fucntions written in Python as well as AWS API Gateway.

## Timeline of remaining tasks

The Open MPIC project is currently under development. The pre-alpha release includes support for the HTTP and DNS domain validation methods using Amazon Web Services Lambda and API Gateway. The work items remaining to a feature-complete production-level product include the following: (subject to change)

- Full conformance to the published [API specification](https://github.com/open-mpic/open-mpic-specification). Because development on the current implementation began as we were standardizing the API specification, there are currently some discrepancies that we plan to resolve. This update will make calls to the lambda API compliant with the specification. Tentative completion date: 6/10/2024
- Automatic provisioning of lambda functions based on a configuration file. This will eliminate the need to create the lambda functions one by one and simply allow a single config file to specify the entire system configuration which is then deployed automatically. Tentative completion date: 7/10/2024
- API Testing scripts and usage examples. Tentative completion date: 7/25/2024
- Support for additional features in the API specification. Some features in the API specification (like TLS-ALPN support) are not in the current prototype. We plan to make the prototype a complete implementation of the API specification. Tentative completion date: 8/10/2024
- Final testing and debugging. Tentative completion date: 9/1/2024

Throughout the development process, we will address any GitHub issues raised, and may modify the API accordingly. We also welcome pull requests from the general community.

## Tasks without assigned timelines
There are several features that may be of interest to the community but we don't yet have a specific completion timeline. These may be given higher priority based on feedback and community interest.

- Support for retrieval of contact information from whois and DNS for the purpose of validation. Several validation methods require contact information to be retrieved via multiple perspectives (e.g., email to domain CAA contact) which is then used in a subsequent validation step (that may not actually require MPIC). The API could support this by allowing a single API call to retrieve the contact info and then perform a set comparison (based on the quorum policy) to return contact info that could be used for validation.
- Support for CAA extensions. CAA issue tags can potentially have extensions to specify things like account ID or validation method per [RFC 8657](https://datatracker.ietf.org/doc/html/rfc8657). The API could potentially take validation method or account id as an optional parameter and perform the processing on these CAA extensions to have them correctly impact the API response.

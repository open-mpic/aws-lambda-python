import dns.resolver
import json
import os
import requests

# TODO extract into a separate module to test


# TODO format perspective response to match API description.
# noinspection PyUnusedLocal
def lambda_handler(event, context):
    region = os.environ['AWS_REGION']
    
    domain_or_ip_target = event['domain_or_ip_target']
    
    # TODO: add some string format validation/error case checking
    valid_method = event['validation_method']
    valid_params = event['validation_params']

    if valid_method == 'http_generic':
        challenge_path = valid_params['path']
        challenge_url = f"http://{domain_or_ip_target}/{challenge_path}"  # noqa E501 (http)
        expected = valid_params['expected_challenge']

        r = requests.get(challenge_url)
    
        if r.status_code == requests.codes.OK:
            result = r.text.strip()
            return {
                'status_code': 200,
                'headers': {
                    'Content-Type': 'application/json'
                    },
                'body': json.dumps({
                    'region': region,
                    'result': result,  # r.data.decode().rstrip()
                    'valid_for_issuance': (result == expected)
                    })
            }
        else:
            return {
                'status_code': r.status_code,
                'headers': {
                    'Content-Type': 'application/json'
                    },
                'body': {
                    'error': r.reason
                    }
            }
    elif valid_method == 'dns_generic':
        challenge_prefix = valid_params['prefix']
        record_type = dns.rdatatype.from_text(valid_params['record_type'])
        name_to_resolve = f'{challenge_prefix}.{domain_or_ip_target}' if len(challenge_prefix) > 0 else f'{domain_or_ip_target}'
        expected = valid_params['expected_challenge']
        
        print(f'Resolving {record_type.name} for {name_to_resolve}...')
        try:
            resp = dns.resolver.resolve(name_to_resolve, record_type)
            record_data_as_text = []
            for response_answer in resp.response.answer:
                if response_answer.rdtype == record_type:
                    for record_data in response_answer:
                        record_data_as_text.append(record_data.to_text()[1:-1])  # need to remove enclosing quotes
            return {
                'status_code': 200,
                'headers': {
                    'Content-Type': 'application/json'
                    },
                'body': json.dumps({
                    'region': region,
                    'result': record_data_as_text,
                    'valid_for_issuance': any([_ == expected for _ in record_data_as_text])
                    })
            }
        except dns.exception.DNSException as e:
            return {
                'status_code': 404,
                'headers': {
                    'Content-Type': 'application/json'
                    },
                'body': {
                    'error': str(e)
                    }
            }

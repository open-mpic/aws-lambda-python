import dns.resolver
import json
import os
import sys
import requests


def lambda_handler(event, context):

    region = os.environ['AWS_REGION']
    
    identifier = event['identifier']
    
    # TODO: add some string format validation/error case checking
    valid_method = event['validation-method']
    valid_params = event['validation-params']


    if valid_method == 'http':
    
        challenge_path = valid_params['path']
        challenge_url = f"http://{identifier}/{challenge_path}"
        expected = valid_params['expected-value']

        r = requests.get(challenge_url)
    
        if r.status_code == requests.codes.OK:
            result = r.text.strip()
            return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json'
                },
            'body': json.dumps({
                'Region': region,
                'Result': result, # r.data.decode().rstrip()
                'ValidForIssue': (result == expected)
                })
            }
        else:
            return {
            'statusCode': r.status_code,
            'headers': {
                'Content-Type': 'application/json'
                },
            'body': {
                'Error': r.reason
                }
            }
    elif valid_method == 'dns':
        
        challenge_prefix = valid_params['prefix']
        rdtype = dns.rdatatype.from_text(valid_params['record-type'])
        name_to_resolve = f'{challenge_prefix}.{identifier}'
        expected = valid_params['expected-value']
        
        print(f'Resolving {rdtype.name} for {name_to_resolve}...')
        try:
            resp = dns.resolver.resolve(name_to_resolve, rdtype)
            txts = []
            for ans in resp.response.answer:
                if ans.rdtype == rdtype:
                    for rdata in ans:
                        txts.append(rdata.to_text()[1:-1]) # need to remove enclosing quotes
            return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json'
                },
            'body': json.dumps({
                'Region': region,
                'Result': txts,
                'ValidForIssue': any([_ == expected for _ in txts])
                })
            }
        except dns.exception.DNSException as e:
            return {
            'statusCode': 404,
            'headers': {
                'Content-Type': 'application/json'
                },
            'body': {
                'Error': str(e)
                }
            }
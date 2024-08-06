import json


class MpicResponseBuilder:
    # FIXME: This method is expected to be implemented in the future
    @staticmethod
    def build_response(status_code, response_body):
        return {
            'statusCode': status_code,
            'body': json.dumps(response_body)
        }
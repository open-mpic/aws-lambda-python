import pytest


class TestMpicCoordinatorLambda:
    @staticmethod
    @pytest.fixture(scope='class')
    def set_env_variables():
        envvars = {
            'perspective_names': 'arin.us-east-1|arin.us-west-1|ripe.eu-west-2|ripe.eu-central-2|apnic.ap-northeast-1|apnic.ap-south-2',
            'validator_arns': 'arn:aws:acm-pca:us-east-1:123456789012:validator/arin.us-east-1|arn:aws:acm-pca:us-west-1:123456789012:validator/arin.us-west-1|arn:aws:acm-pca:eu-west-2:123456789012:validator/ripe.eu-west-2|arn:aws:acm-pca:eu-central-2:123456789012:validator/ripe.eu-central-2|arn:aws:acm-pca:ap-northeast-1:123456789012:validator/apnic.ap-northeast-1|arn:aws:acm-pca:ap-south-2:123456789012:validator/apnic.ap-south-2',
            'caa_arns': 'arn:aws:acm-pca:us-east-1:123456789012:caa/arin.us-east-1|arn:aws:acm-pca:us-west-1:123456789012:caa/arin.us-west-1|arn:aws:acm-pca:eu-west-2:123456789012:caa/ripe.eu-west-2|arn:aws:acm-pca:eu-central-2:123456789012:caa/ripe.eu-central-2|arn:aws:acm-pca:ap-northeast-1:123456789012:caa/apnic.ap-northeast-1|arn:aws:acm-pca:ap-south-2:123456789012:caa/apnic.ap-south-2',
            'default_perspective_count': '3',
            'enforce_distinct_rir_regions': '1',  # TODO may not need this...
            'hash_secret': 'test_secret',
            'caa_domains': 'example.com|example.net|example.org'
        }
        with pytest.MonkeyPatch.context() as class_scoped_monkeypatch:
            for k, v in envvars.items():
                class_scoped_monkeypatch.setenv(k, v)
            yield class_scoped_monkeypatch  # restore the environment afterward


if __name__ == '__main__':
    pytest.main()

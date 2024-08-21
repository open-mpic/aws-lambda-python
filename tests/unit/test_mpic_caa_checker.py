import pytest
from aws_lambda_python.mpic_caa_checker.mpic_caa_checker import MpicCaaChecker


# noinspection PyMethodMayBeStatic
class TestMpicCaaChecker:
    @pytest.mark.parametrize('value_list, caa_domains', [
        (['ca1.org'], ['ca1.org']),
        (['ca1.org', 'ca2.com'], ['ca2.com']),
        (['ca1.org', 'ca2.com'], ['ca3.org', 'ca1.org']),
    ])
    def does_value_list_permit_issuance__should_return_true_given_one_value_found_in_caa_domains(self, value_list, caa_domains):
        result = MpicCaaChecker.does_value_list_permit_issuance(value_list, caa_domains)
        assert result is True

    def does_value_list_permit_issuance__should_return_false_given_value_not_found_in_caa_domains(self):
        value_list = ['letsencrypt.org']
        caa_domains = ['google.com']
        result = MpicCaaChecker.does_value_list_permit_issuance(value_list, caa_domains)
        assert result is False

    def does_value_list_permit_issuance__should_return_false_given_only_values_with_extensions(self):
        value_list = ['0 issue "letsencrypt.org; policy=ev"']
        caa_domains = ['letsencrypt.org']
        result = MpicCaaChecker.does_value_list_permit_issuance(value_list, caa_domains)
        assert result is False

    def does_value_list_permit_issuance__should_ignore_whitespace_around_values(self):
        value_list = ['  ca1.org  ']
        caa_domains = ['ca1.org']
        result = MpicCaaChecker.does_value_list_permit_issuance(value_list, caa_domains)
        assert result is True


if __name__ == '__main__':
    pytest.main()

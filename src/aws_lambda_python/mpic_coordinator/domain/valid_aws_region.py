class AwsRegion:
    def __init__(self, region_code: str, region_name, list_of_regions_within_500_km: list):
        self.region_code = region_code
        self.regions_within_500_km = list_of_regions_within_500_km

class ValidAwsRegion(Enum):
    AF_SOUTH_1 = AwsRegion('af-south-1', 'Africa (Cape Town)', [])
    AP_EAST_1 = AwsRegion('ap-east-1', 'Asia Pacific (Hong Kong)', [])
    AP_NORTHEAST_1 = AwsRegion('ap-northeast-1', 'Asia Pacific (Tokyo)', [])
    AP_NORTHEAST_2 = AwsRegion('ap-northeast-2', 'Asia Pacific (Seoul)', [])
    AP_NORTHEAST_3 = AwsRegion('ap-northeast-3', 'Asia Pacific (Osaka)', [])
    AP_SOUTH_1 = AwsRegion('ap-south-1', 'Asia Pacific (Mumbai)', [])
    AP_SOUTH_2 = AwsRegion('ap-south-2', 'Asia Pacific (Hyderabad)', [])
    AP_SOUTHEAST_1 = AwsRegion('ap-southeast-1', 'Asia Pacific (Singapore)', [])
    AP_SOUTHEAST_2 = AwsRegion('ap-southeast-2', 'Asia Pacific (Sydney)', [])
    AP_SOUTHEAST_3 = AwsRegion('ap-southeast-3', 'Asia Pacific (Jakarta)', [])
    AP_SOUTHEAST_4 = AwsRegion('ap-southeast-4', 'Asia Pacific (Melbourne)', [])
    CA_CENTRAL_1 = AwsRegion('ca-central-1', 'Canada (Central)', [])
    CA_WEST_1 = AwsRegion('ca-west-1', 'Canada (Calgary)', [])
    CN_NORTH_1 = AwsRegion('cn-north-1', 'China (Beijing)', [])
    CN_NORTHWEST_1 = AwsRegion('cn-northwest-1', 'China (Ningxia)', [])
    EU_CENTRAL_1 = AwsRegion('eu-central-1', 'Europe (Frankfurt)', [])
    EU_CENTRAL_2 = AwsRegion('eu-central-2', 'Europe (Zurich)', [])
    EU_NORTH_1 = AwsRegion('eu-north-1', 'Europe (Stockholm)', [])
    EU_SOUTH_1 = AwsRegion('eu-south-1', 'Europe (Milan)', [])
    EU_WEST_1 = AwsRegion('eu-west-1', 'Europe (Ireland)', [])
    EU_WEST_2 = AwsRegion('eu-west-2', 'Europe (London)', [EU_WEST_3])
    EU_WEST_3 = AwsRegion('eu-west-3', 'Europe (Paris)', [EU_WEST_2])
    IL_CENTRAL_1 = AwsRegion('il-central-1', 'Israel (Tel Aviv)', [])
    ME_CENTRAL_1 = AwsRegion('me-central-1', 'Middle East (UAE)', [])
    ME_SOUTH_1 = AwsRegion('me-south-1', 'Middle East (Bahrain)', [])
    SA_EAST_1 = AwsRegion('sa-east-1', 'South America (Sao Paulo)', [])
    US_EAST_1 = AwsRegion('us-east-1', 'US East (N. Virginia)', [])
    US_EAST_2 = AwsRegion('us-east-2', 'US East (Ohio)', [])
    US_WEST_1 = AwsRegion('us-west-1', 'US West (N. California)', [])
    US_WEST_2 = AwsRegion('us-west-2', 'US West (Oregon)', [])
    # US_GOV_EAST_1 = AwsRegion('us-gov-east-1', 'AWS GovCloud (US-East)', [])
    # US_GOV_WEST_1 = AwsRegion('us-gov-west-1', 'AWS GovCloud (US-West)', [])


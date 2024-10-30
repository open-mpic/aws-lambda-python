class MpicRequestValidationIssue:
    def __init__(self, validation_message, *message_args):
        self.issue_type = validation_message.key
        self.message = validation_message.message.format(*message_args)

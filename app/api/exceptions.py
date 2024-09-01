from rest_framework import status
from rest_framework.exceptions import APIException


class DuplicateSubmissionError(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "The user has already answered the task"


class ProfileAddedError(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "The profile has already been added to the user"

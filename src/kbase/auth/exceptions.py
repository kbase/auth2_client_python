""" Exceptions thrown by the auth library. """


class AuthenticationError(Exception):
    """ An error thrown from the authentication service. """


class InvalidTokenError(AuthenticationError):
    """ An error thrown when a token is invalid. """


class InvalidUserError(AuthenticationError):
    """ An error thrown when a username is invalid. """

#!/usr/bin/python2.7
#
# Copyright (c) 2015, Oracle and/or its affiliates. All rights reserved.
#

import ctiutils
import commands


class ExecuteException(Exception):
    pass


class NoneException(Exception):
    pass


class ReturnException(Exception):
    pass


class LoginException(Exception):
    pass


def info_print(string):
    print "INFO : %s" % string


def info_report(string):
    ctiutils.cti_report("%s" % string)


def info_print_report(string):
    info_print(string)
    info_report(string)


def error_print(string):
    print "ERROR: %s" % string


def error_report(string):
    ctiutils.cti_report("%s" % string)


def error_print_report(string):
    error_print(string)
    error_report(string)


def warn_print(string):
    print "WARN : %s" % string


def warn_report(string):
    ctiutils.cti_report("%s" % string)


def warn_print_report(string):
    warn_print(string)
    warn_report(string)


def execute(cmd, check=True):
    (status, output) = commands.getstatusoutput(cmd)
    if check:
        if status != 0:
            raise ExecuteException(
                "Execution of [%s] failed:\n%s" %
                (cmd, output))
    return output


def get_value_from_string(string):
    """
    Purpose:
        get the value from a format string
        e.g. failure-policy=ignore
    Arguments:
        string -
    Return:
        value - the value in the string
    """
    value = string.split("=")[1].strip().rstrip('\r\n')
    return value

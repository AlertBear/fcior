#!/usr/bin/python2.7
#
# Copyright (c) 2015, Oracle and/or its affiliates. All rights reserved.
#


import time
import pexpect
from basic import *

class Host(object):

    def __init__(self, hostname, password, username='root'):
        self.hostname = hostname
        self.username = username
        self.password = password  # ssh root password

    def login(self):
        cmd_ssh = 'ssh -l {0} {1}'.format(self.username, self.hostname)
        cld = pexpect.spawn(cmd_ssh)
        cld.send('\r')
        child = pexpect.spawn(cmd_ssh)

        interact_log = "/tmp/ssh_interact"
        child.logfile = open(interact_log, 'a+')

        child.send('\r')
        prompts = [
            'Password:',
            '~#',
            'continue connecting (yes/no)?',
            pexpect.TIMEOUT,
            pexpect.EOF]
        while True:
            try:
                i = child.expect(prompts, timeout=60)
            except Exception:
                raise LoginException(
                    "Failed to login %s due to null expect reason" %
                    self.hostname)
            if i == 0:
                child.sendline(self.password)
            elif i == 1:
                cld.close()
                return child
            elif i == 2:
                child.sendline('yes\r')
            elif i == 3:
                raise LoginException(
                    "Failed to login %s due to incorrect password or TIMEOUT" %
                    self.hostname)
            elif i == 4:
                raise LoginException("Failed to login %s due to EOF" % self.hostname)

    def send_command(self, cmd, expectation='~#', timeout=60, check=True):
        """
        Purpose:
            Execute the command in this domain without any output
        Arguments:
            cmd - Command to be executed
            expectation - Expect the display after the execution
            timeout - Exceed the timeout during the execution will
                raise the timeout exception
            check - True: Check whether the execution be successful or not
                    False: No check after the execution
        Return:
            None
        """
        cldconsole = self.login()
        cldconsole.sendline(cmd)
        cmd_clear = cmd
        # Clear the echo of the command once send
        cldconsole.expect(cmd_clear)

        try:
            cldconsole.expect(expectation, timeout)
        except Exception as e:
            raise ExecuteException(
                "Execution of [{0}] in {1} failed due to:\n{2}".format(
                    cmd,
                    self.hostname,
                    e))
        if check:
            # Check to ensure the command has been successfully executed
            cldconsole.sendline('echo $?')
            i = cldconsole.expect(
                ['0', '1', pexpect.TIMEOUT, pexpect.EOF], timeout)
            if i != 0:
                raise ExecuteException(
                    "Execution of [{0}] failed in {1}".format(
                        cmd,
                        self.hostname))
        cldconsole.close()
        time.sleep(0.2)

    def return_command(self, cmd, expectation='~#', timeout=60, check=True):
        """
        Purpose:
            Get the execution output of a command in domain
        Arguments:
            cmd - Command to be executed
            expectation - Expect the display after the execution
            timeout - Exceed the timeout during the execution will
                raise the timeout exception
        Return:
            output - The output of the execution in domain
        """
        cldconsole = self.login()
        if expectation == '~#':
            expectation = 'root@.*:~#'
        cldconsole.sendline(cmd)
        cmd_clear = cmd
        # Clear the echo of the command once send
        cldconsole.expect(cmd_clear)
        try:
            cldconsole.expect(expectation, timeout)
        except Exception as e:
            raise Exception(
                "Failed to execute [%s] in domain due to:\n %s" % (cmd, e))
        output = cldconsole.before
        output = output.strip(cmd_clear).strip('\r\n')
        if check:
            cldconsole.sendline('echo $?')
            i = cldconsole.expect(
                ['0', '1', pexpect.TIMEOUT, pexpect.EOF], timeout)
            if i != 0:
                raise ReturnException(
                    "Execution of [%s] failed in %s:\n%s" %
                    (cmd, self.hostname, output))
        cldconsole.close()
        time.sleep(0.2)
        return output

#!/usr/bin/python2.7
#
# Copyright (c) 2015, Oracle and/or its affiliates. All rights reserved.
#


import commands
import time
import pexpect
import re
import os
import tempfile
import error


def execute(cmd):
    (status, output) = commands.getstatusoutput(cmd)
    if status != 0:
        raise error.ExecuteException(
            "Execution of [%s] failed:\n%s" %
            (cmd, output))
    return output


class Ldom(object):

    def __init__(self, name, password, port):
        self.name = name
        self.password = password  # Telnet root password
        self.port = port  # Console port

    def login(self):
        cmd_telnet = 'telnet 0 ' + str(self.port)
        cld = pexpect.spawn(cmd_telnet)
        cld.send('\r')
        child = pexpect.spawn(cmd_telnet)

        # Save the interaction log, test user could review to check the whole
        # process.
        interact_log = os.getenv("INT_LOG")
        child.logfile = open(interact_log, 'a+')

        child.send('\r')
        prompts = [
            'console login:',
            'Password:',
            '~#',
            pexpect.TIMEOUT,
            pexpect.EOF,
            'You do not have write access']
        while True:
            try:
                i = child.expect(prompts, timeout=300)
            except Exception:
                raise error.LoginException(
                    "Failed to login due to null expect reason")
            if i == 0:
                child.sendline('root')
            elif i == 1:
                child.sendline(self.password)
            elif i == 2:
                cld.close()
                return child
            elif i == 3:
                raise error.LoginException(
                    "Failed to login due to incorrect password or TIMEOUT")
            elif i == 4:
                raise error.LoginException("Failed to login due to EOF")
            elif i == 5:
                child.send('~wy\r')

    def sendcmd(self, cmd, expectation='~#', timeout=60, check=True):
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
        try:
            cldconsole.expect(expectation, timeout)
        except Exception as e:
            raise error.ExecuteException(
                "Execution of [{0}] in {1} failed due to:\n{2}".format(
                    cmd,
                    self.name,
                    e))
        if check:
            # Check to ensure the command has been successfully executed
            cldconsole.sendline('echo $?')
            i = cldconsole.expect(
                ['0', '1', pexpect.TIMEOUT, pexpect.EOF], timeout)
            if i != 0:
                raise error.ExecuteException(
                    "Execution of [{0}] failed in {1}".format(
                        cmd,
                        self.name))
        cldconsole.close()
        time.sleep(0.2)

    def retsend_one_line(self, cmd, expectation='~#', timeout=60):
        """
        Purpose:
            Get the execution output of a command in domain,
            ensure there is only one line of the output
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
        try:
            cldconsole.expect(expectation, timeout)
        except Exception as e:
            raise Exception(
                "Execution of [%s] failed in %s due to:\n %s" %
                (cmd, self.name, e))
        cldconsole.sendline('echo $?')
        i = cldconsole.expect(
            ['0', '1', pexpect.TIMEOUT, pexpect.EOF], timeout)
        if i != 0:
            raise error.ReturnException(
                "Execution of [%s] failed in %s" % (cmd, self.name))
        else:
            cldconsole.sendline(cmd)
            cldconsole.readline()
            cldconsole.readline()
            output = cldconsole.readline()
        cldconsole.close()
        return output

    def retsend(self, cmd, expectation='~#', timeout=60, check=True):
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
        output = output.strip('cmd_clear').strip('\r\n')
        if check:
            cldconsole.sendline('echo $?')
            i = cldconsole.expect(
                ['0', '1', pexpect.TIMEOUT, pexpect.EOF], timeout)
            if i != 0:
                raise error.ReturnException(
                    "Execution of [%s] failed in %s:\n%s" %
                    (cmd, self.name, output))
        cldconsole.close()
        time.sleep(0.2)
        return output

    def save_hotplug_log(self, directory):
        """
        Purpose:
            Save the output of the "hotplug list -lv", this mainly used to
            analyse the hotplug related information.
        Arguments:
            directory - Directory to save the log
        Return:
            logfile - Path of the log
        """
        now = time.strftime("%H%M%S")
        logfile_path_tmp = directory
        # Name the file as hotplug.{currrent time}
        logfile = "{0}/{1}".format(logfile_path_tmp, 'hotplug.' + now)
        cmd_touch_logfile = "touch %s" % logfile
        execute(cmd_touch_logfile)
        cmd_hotplug = "hotplug list -lv"
        output_hotplug = self.retsend(cmd_hotplug, timeout=180)
        with open(logfile, 'r+') as fo:
            fo.write(output_hotplug)
        return logfile

    def save_fcinfo_log(self, directory):
        """
        Purpose:
            Save the output of "fcinfo hab-port" of the domain
        Arguments:
            directory - Directory to save the log
        Return:
            logfile - Path of the log
        """
        now = time.strftime("%H%M%S")
        logfile_path_tmp = directory
        # Name the file as fcinfo.{current time}
        logfile = "%s/%s" % (logfile_path_tmp, 'fcinfo.' + now)
        cmd_touch_logfile = 'touch %s' % logfile
        try:
            execute(cmd_touch_logfile)
        except Exception as e:
            raise e
        cmd_fcinfo = "fcinfo hba-port | grep HBA"
        try:
            output_fcinfo = self.retsend(cmd_fcinfo, timeout=180)
        except error.ReturnException:
            output_fcinfo = None
        if output_fcinfo is None:
            return logfile
        with open(logfile, 'r+') as fo:
            fo.write(output_fcinfo)
        return logfile

    def save_path_log(self, directory):
        """
        Purpose:
            Save the output of "luxadm probe" to a logfile
        Arguments:
            directory - Directory to save the log
        Return:
            logfile - Path of the log
        """
        now = time.strftime("%H%M%S")
        logfile_path_tmp = directory
        # Name the file as path.{current time}
        logfile = "%s/%s" % (logfile_path_tmp, 'path.' + now)
        cmd_touch_logfile = 'touch %s' % logfile
        try:
            execute(cmd_touch_logfile)
        except Exception as e:
            raise e
        cmd_luxadm = "luxadm probe | grep Path"
        try:
            output_luxadm = self.retsend(cmd_luxadm, timeout=180)
        except error.ReturnException:
            output_luxadm = None
        if output_luxadm is None:
            return logfile
        with open(logfile, 'r+') as fo:
            fo.write(output_luxadm)
        return logfile

    def save_io_data(self, disk, directory):
        """
        Purpose:
            Save the iostat data of a disk
        Arguments:
            disk - Disk name
            directory - Directory to save the log
        Return:
            logfile - Path of the logfile
        """
        now = time.strftime("%H%M%S")
        logfile_path_tmp = directory
        # Name the file as iodata.{current time}
        logfile = "%s/%s" % (logfile_path_tmp, 'iodata.' + now)
        cmd_touch_logfile = "touch %s" % logfile
        try:
            execute(cmd_touch_logfile)
        except Exception as e:
            raise e
        # Use "iostat" to get the io data
        cmd_iostat = "iostat -xn {0} 5 3 | grep {1}".format(disk, disk)
        try:
            output_iostat = self.retsend(cmd_iostat)
        except error.ReturnException:
            output_iostat = None
        if output_iostat is None:
            return logfile
        with open(logfile, 'r+') as fo:
            fo.write(output_iostat)
        return logfile

    def get_vf_hotplug_dev(self, vf):
        """
        Purpose:
            Get the hotplug dev info
        Arguments:
            vf - VF name
        Return:
            hotplug_dev - e.g /pci@380/pci@1/pci@0/pci@5/SUNW,qlc@0,14
        """
        # Get through "ldm list-io -p"
        cmd_list_io = 'ldm list-io -p | grep %s' % vf
        output_list_io = execute(cmd_list_io)
        # output instance:
        # |dev=pci@700/pci@1/pci@0/pci@4/SUNW,emlxs@0
        # |alias=/SYS/PCI-EM14/IOVFC.PF0|status=|domain=fc-nprd3
        # |type=PF|bus=pci_3
        # Split to get the second element of the output
        hotplug_dev = output_list_io.split("|")[1].strip()
        # Split to get the second element
        hotplug_dev = hotplug_dev.split('=')[1].strip()
        hotplug_dev = '/' + hotplug_dev  # Add '/' to the header
        return hotplug_dev

    def get_vf_hotplug_path_port_status(self, vf, logfile=None):
        """
        Purpose:
            Get the hotplug path port and status of the vf in the domain
        Arguments:
            vf - VF name
            logfile - not None: get the info from this specified logfile
        Return:
            path_port_status_dict - The specified pcie device hotplug status
            e.g.{"hotplug_path":hotplug_path, "hotplug_port":hotplug_port,
                "hotplug_status":hotplug_status}
        """
        hotplug_dev = self.get_vf_hotplug_dev(vf)

        if logfile is None:
            safe, logfile = tempfile.mkstemp()
            cmd_hotplug = "hotplug list -lv"
            output_hotplug = self.retsend(cmd_hotplug, timeout=180)
            with open(logfile, 'r+') as fo:
                fo.write(output_hotplug)

        replace_str = hotplug_dev.split('/')[-1].strip().split('@')[0]
        hotplug_dev_format = hotplug_dev.replace(
            '/', '\/').replace(replace_str, '.*')

        # Get the line number of hotplug_dev from the logfile which stored the
        # hotplug info
        cmd_get_line_num = 'sed -n "/^{0}.$/=" {1}'.format(
            hotplug_dev_format,
            logfile)
        output_get_line_num = execute(cmd_get_line_num)
        dev_line_number = int(output_get_line_num)

        # Calculate the line number of hotplug_path_port_status
        path_port_status_line_number = dev_line_number - 1
        cmd_path_port_status = 'sed -n "{0}p" {1}'.format(
            path_port_status_line_number,
            logfile)
        output_path_port_status = execute(cmd_path_port_status)
        # Instance: /pci@380/pci@1/pci@0/pci@6  <pci.0,2>  ONLINE
        path_port_status = output_path_port_status
        hotplug_path = path_port_status.split()[0].strip().lstrip(
            "\r\n")  # The first element path_port_status
        # The second element of path_port_status
        hotplug_port = path_port_status.split()[1].strip('<>').strip()
        hotplug_status = path_port_status.split()[2].strip().rstrip(
            "\r\n")  # The last element of path_port_status
        path_port_status_dict = {
            'hotplug_path': hotplug_path,
            'hotplug_port': hotplug_port,
            'hotplug_status': hotplug_status}
        return path_port_status_dict

    def get_vf_hotplug_status(self, vf, logfile=None):
        """
        Purpose:
            Get current hotplug status of the vf
        Arguments:
            vf - VF name
        Return:
            hotplug_status
        """
        dev_path_port_status_dict = self.get_vf_hotplug_path_port_status(
            vf,
            logfile)
        hotplug_status = dev_path_port_status_dict['hotplug_status']
        return hotplug_status

    def get_vf_hotplug_status_by_path_port(self, path, port, logfile=None):
        """
        Purpose:
            Get current hotplug status of the vf
        Arguments:
            vf - VF name
        Return:
            hotplug_status
        """
        if logfile is None:
            safe, logfile = tempfile.mkstemp()
            cmd_hotplug = "hotplug list -lv"
            output_hotplug = self.retsend(cmd_hotplug, timeout=180)
            with open(logfile, 'r+') as fo:
                fo.write(output_hotplug)

        cmd_get_path_port_status = 'grep {0} {1}|grep {2}'.format(
            path,
            logfile,
            port)
        output_path_port_status = execute(cmd_get_path_port_status)
        hotplug_status = output_path_port_status.split()[2]
        return hotplug_status

    def get_vf_logical_path(self, vf):
        """
        Purpose:
            Get the vf logical path
        Arguments:
            vf - VF name
        Return:
            logical_path - e.g./dev/rdsk/c0t600A0B80002A38460000F80752F6EB7Ed0s2
        """
        # Get hotplug_dev of the vf, be used later
        hotplug_dev = self.get_vf_hotplug_dev(vf)

        # Get all the logical paths in the domain
        cmd_luxadm = "luxadm probe | grep Path"
        try:
            output_luxadm = self.retsend(cmd_luxadm, timeout=180)
        except error.ReturnException:
            return None
        pattern = re.compile(r'\/dev\/.*')
        match = pattern.findall(output_luxadm)
        if match is None:
            return None
        all_logical_paths = match
        logical_path = None

        # There maybe several logical paths,
        # find the mapping logical path of the VF according the hotplug_dev
        for logical_path_item in all_logical_paths:
            logical_path_item = logical_path_item.strip().rstrip(
                '\r\n').lstrip('\r\n')
            cmd = "prtconf -v {0}|grep pci|grep {1}".format(
                logical_path_item,
                hotplug_dev)
            try:
                self.sendcmd(cmd)
            except error.ExecuteException:
                continue
            else:
                logical_path = logical_path_item
                break
        return logical_path

    def check_vf_mpxio(self, vf):
        """
        Purpose:
            Check whether the vf is MPxIO with another vf in domain
        Arguments:
            vf - VF name
        Return:
            True or False
        """
        # Get hotplug_dev of the vf, be used later
        hotplug_dev = self.get_vf_hotplug_dev(vf)

        # Get all the logical paths in the domain
        cmd_luxadm = "luxadm probe | grep Path"
        try:
            output_luxadm = self.retsend(cmd_luxadm, timeout=180)
        except error.ReturnException:
            return False
        pattern = re.compile(r'\/dev\/.*')
        match = pattern.findall(output_luxadm)
        if match is None:
            return False
        all_logical_paths = match

        logical_path = None
        # There maybe several logical paths,
        # find the mapping logical path of the VF according the hotplug_dev
        for logical_path_item in all_logical_paths:
            logical_path_item = logical_path_item.strip().rstrip(
                '\r\n').lstrip('\r\n')
            cmd = "prtconf -v {0}|grep pci|grep {1}".format(
                logical_path_item,
                hotplug_dev)
            try:
                self.sendcmd(cmd)
            except error.ExecuteException:
                continue
            else:
                logical_path = logical_path_item
                break

        if not logical_path:
            return False
        else:
            cmd = "prtconf -v %s|grep pci" % logical_path
            try:
                output_luxadm = self.retsend(cmd)
            except error.ReturnException:
                return False
            pattern = re.compile(r'Path')
            match = pattern.findall(output_luxadm)
            if len(match) < 2:
                return False
            else:
                bus_path = hotplug_dev.split('/')[1]
                for item in match:
                    each_path = item.split(':')[1].strip()
                    if each_path.split('/')[1] != bus_path:
                        return True
                    else:
                        return False

    def check_vf_io_workload_on(self, vf, logfile=None):
        """
        Purpose:
            Check whether the vf has io traffic
        Arguments:
            vf - VF name
        Return:
            True - The vf has io traffic
            False - The vf does not have io traffic
        """
        io_workload_on = False
        # Get the logical path of the vf
        logical_path = self.get_vf_logical_path(vf)

        if logical_path is None:  # VF is not mapping to any logical path
            return False
        # Parse the disk from the logical path
        disk = logical_path.split('/')[3][:-2]

        if logfile is None:
            safe, logfile = tempfile.mkstemp()  # Create a temp file
            # Get the io data by "iostat" and save to the above temp file
            cmd_iostat = "iostat -xn {0} 5 3 | grep {1}".format(disk, disk)
            output_iostat = self.retsend(cmd_iostat, timeout=180)
            with open(logfile, 'r+') as fo:
                fo.write(output_iostat)

        # IO traffic check
        try:
            fo = open(logfile, 'r')
        except IOError as e:
            raise e
        else:
            io_check_flag = 0
            first_data = True  # Whether it is the first line of io data

            for line in fo:  # Loop to read and analyse the data
                if line is None:
                    break
                pattern = re.compile(r'{0}'.format(disk))
                match = pattern.search(line)
                if match is None:
                    continue
                # Ignore the first line of io data due to it is previous one
                if first_data:
                    first_data = False
                    continue
                read_data = line.split()[2]
                write_data = line.split()[3]
                io_data = float(read_data) + float(write_data)
                if io_data == 0:  # IO traffic(read and write) is zero
                    break       # No need to continue check
                io_check_flag += 1

            # If IO traffic in first period and second period are both not
            # zero, that means io is on.
            if io_check_flag >= 2:
                io_workload_on = True
        finally:
            fo.close()
        return io_workload_on

    def run_io_workload_on_vf(self, vf):
        """
        Purpose:
            Run I/O workload on the vf
        Arguments:
            vf - VF name
        Return:
            None
        """
        logical_path = self.get_vf_logical_path(vf)
        disk = logical_path.split("/")[-1][:-2]  # Parse /dev/rdsk/... to disk

        # First to create a zfs pool
        cmd_create_pool = "zpool create -f ior_pool %s" % disk
        self.sendcmd(cmd_create_pool)
        cmd_pool_status = 'zpool status ior_pool | sed -n "2p"'
        output_pool_status = self.retsend(cmd_pool_status)
        if output_pool_status.split(':')[1].strip() != 'ONLINE':
            raise Exception("ior_pool is not ONLINE")

        # Then to create a zfs filesystem under above pool
        cmd_create_zfs = "zfs create ior_pool/fs"
        self.sendcmd(cmd_create_zfs)

        # Check whether the run_io.sh exists
        cmd_test_file = "test -f ~/run_io.sh"
        try:
            self.sendcmd(cmd_test_file)
        except error.ExecuteException:
            raise Exception("run_io.sh doesn't exist")
        # If run_io.sh exists, use to run io traffic in the domain
        cmd_run = 'nohup ~/run_io.sh &'
        self.sendcmd(cmd_run)

        # Wait 5 seconds to check the io traffic whether is on
        time.sleep(5)
        if not self.check_vf_io_workload_on(vf):
            raise Exception("run_io.sh doesn't not run as expected")

    def run_vdbench_on_vf(self, vf):
        """
        Purpose:
            Run vdbench on the vf
        Arguments:
            vf - VF name
        Return:
            None
        """
        # Get the logical path and disk of the vf
        logical_path = self.get_vf_logical_path(vf)
        # Parse /dev/rdsk/... to disk format
        disk = logical_path.split("/")[-1][:-2]

        # Test whether the vdbench file exist
        vdbench_path = os.getenv("VDBENCH_PATH")
        cmd_test_file = 'test -d %s' % vdbench_path
        try:
            self.sendcmd(cmd_test_file)
        except error.ExecuteException as e:
            raise Exception("Vdbench doesn't exist")

        # Remove any previous configuration under vdbench
        cmd1 = "rm %s" % (vdbench_path + '/ior.*')
        self.sendcmd(cmd1, check=False)

        # Use the example1 file under vdbench path to configure
        example1 = vdbench_path + '/example1'
        cfg_test = vdbench_path + '/ior.cfg.test'
        cmd2 = "sed '/c0t0d0sx/s/c0t0d0sx/{0}/' {1} > {2}".format(
            disk,
            example1,
            cfg_test)
        self.sendcmd(cmd2)
        cfg = vdbench_path + '/ior.cfg'
        cmd3 = "sed 's/elapsed=10/elapsed=3600/' {0} > {1}".format(
            cfg_test,
            cfg)
        self.sendcmd(cmd3)
        vdbench = vdbench_path + '/vdbench'

        # Use the newly above configuration file to run vdbench in domain
        cmd4 = "nohup {0} -f {1} > /dev/null 2>&1 &".format(vdbench, cfg)
        self.sendcmd(cmd4)
        time.sleep(30)

        # Check whether running vdbench successfully
        if not self.check_vf_io_workload_on(vf):
            raise Exception("Vdbench doesn't not run as expected")

    def reboot(self, count=1, timeout=600):
        """
        Purpose:
            Reboot the domain
        Arguments:
            count - Reboot times
            timeout - If domain doesn't reboot to normal status
                in timeout seconds, will trigger a Exception
        Return:
            None
        """

        i = 0
        cmd = 'reboot'
        while i < count:
            self.sendcmd(cmd, 'console login:', timeout, check=False)
            i += 1

    def panic(self, count=1, timeout=600):
        """
        Purpose:
            Panic the domain
        Arguments:
            count - Panic times
            timeout - If domain doesn't boot to normal status in timeout seconds,
                will trigger a Exception
        Return:
            None
        """
        i = 0
        cmd_panic = 'echo "rootdir/W 0" | mdb -kw'
        # Get debug version by check the printf number in mdb,
        # if num == 2 ,debug =False, else num = 3, debug =True
        cmd_get_debug_version = 'echo "log_init::dis" | mdb -k |grep printf |wc -l'
        printf_num_string = self.retsend_one_line(cmd_get_debug_version)
        printf_num = int(printf_num_string.strip())
        if printf_num == 2:
            debug = False
        else:
            debug = True
        # Test system is a debug one
        if debug:
            # "eset?" may appear
            cmd_telnet = 'telnet 0 ' + str(self.port)
            while i < count:
                self.sendcmd(cmd_panic, 'rootdir:')
                cld = pexpect.spawn(cmd_telnet)
                cld.send('\r')
                child = pexpect.spawn(cmd_telnet)
                child.send('\r')
                prompts = [
                    'eset?',
                    pexpect.TIMEOUT,
                    pexpect.EOF,
                    'You do not have write access']
                while True:
                    try:
                        i = child.expect(prompts, 60)
                    except Exception:
                        raise error.LoginException(
                            "Failed to login due to null expect reason")
                    if i == 0:
                        child.sendline('r')
                        try:
                            child.expect(['console login:'], timeout)
                        except Exception as e:
                            raise error.LoginException(e)
                        else:
                            break
                        finally:
                            cld.close()
                    elif i == 1:
                        raise error.LoginException(
                            "Failed to login due to incorrect password or TIMEOUT")
                    elif i == 2:
                        raise error.LoginException(
                            "Failed to login due to EOF")
                    elif i == 3:
                        child.send('~wy\r')
                        prompts.pop(i)
                cld.close()
                i += 1
        # Test system is not a debug one
        else:
            # Continue panic will reduce the disk space, need delete the newly
            # generated core dump file
            while i < count:
                # Delete the old crash list file
                prev_crash_list = '/var/tmp/fcior/tmp/prev_crash_list'
                post_crash_list = '/var/tmp/fcior/tmp/post_crash_list'
                cmd_delete_compare_file = "rm -f %s %s" % (
                    prev_crash_list, post_crash_list)
                execute(cmd_delete_compare_file)

                # Create the new crash list file before panic
                cmd_touch_prev_crash_list = "touch %s" % prev_crash_list
                execute(cmd_touch_prev_crash_list)
                # Get all the file under /var/crash/ in domain before panic
                cmd_list_prev_crash_dump = "ls /var/crash/"
                try:
                    output_list_prev_crash_dump = self.retsend(
                        cmd_list_prev_crash_dump)
                except error.ReturnException:
                    output_list_prev_crash_dump = None
                if output_list_prev_crash_dump is None:
                    pass
                else:
                    with open(prev_crash_list, 'r+') as fo:
                        fo.write(output_list_prev_crash_dump)

                # Panic the system
                self.sendcmd(cmd_panic, 'console login:', timeout, check=False)

                # Create the new crash list after panic
                cmd_touch_post_crash_list = "touch %s" % post_crash_list
                execute(cmd_touch_post_crash_list)
                # Get the file under /var/crash/ after panic
                cmd_list_post_crash_dump = "ls /var/crash/"
                try:
                    output_list_post_crash_dump = self.retsend(
                        cmd_list_post_crash_dump)
                except error.ReturnException:
                    output_list_post_crash_dump = None
                if output_list_post_crash_dump is None:
                    pass
                else:
                    with open(post_crash_list, 'r+') as fo:
                        fo.write(output_list_post_crash_dump)

                # Get the newly generated coredump file according to diff two
                # files above
                output_diff_two_file = None

                with open(prev_crash_list, 'r') as prev:
                    with open(post_crash_list, 'r') as post:
                        for fprev in prev.readlines():
                            for fpost in post.readlines():
                                for file in fpost.split():
                                    if file not in fprev.split():
                                        output_diff_two_file = file
                                        break

                # Delete the newly generated coredump file
                if output_diff_two_file is not None:
                    cmd_clear_coredump = "rm -rf /var/crash/{0}/*".format(
                        output_diff_two_file)
                    self.sendcmd(cmd_clear_coredump, check=False)
                i += 1

    def offline_vf(self, vf):
        """
        Purpose:
            Hotplug offline the specified vf in the domain
        Arguments:
            vf - VF name
        Return:
            None
        """
        dev_path_port_status_dict = self.get_vf_hotplug_path_port_status(vf)
        hotplug_path = dev_path_port_status_dict.get('hotplug_path')
        hotplug_port = dev_path_port_status_dict.get('hotplug_port')
        cmd = "hotplug offline %s %s" % (hotplug_path, hotplug_port)
        try:
            self.sendcmd(cmd)
        except Exception as e:
            raise Exception(
                "Failed to offline %s in %s due to:\n %s" %
                (vf, self.name, e))

    def online_vf(self, vf):
        """
        Purpose:
            Hotplug online the specified vf in the domain
        Arguments:
            vf - VF name
        Return:
            None
        """
        dev_path_port_status_dict = self.get_vf_hotplug_path_port_status(vf)
        hotplug_path = dev_path_port_status_dict.get('hotplug_path')
        hotplug_port = dev_path_port_status_dict.get('hotplug_port')
        cmd = "hotplug online %s %s" % (hotplug_path, hotplug_port)
        try:
            self.sendcmd(cmd)
        except Exception as e:
            raise Exception("Failed to online %s due to:\n %s" % (vf, e))

    def check_vf_port_wwn_status(self, port_wwn, logfile=None):
        """
        Purpose:
            Check the vf mapping port_wwn(fcinfo hba-port)
            whether can be seen from logfile
        Arguments:
            vf - VF name
            logfile - The output of "fcinfo hba-port|grep HBA" logfile
        Return:
            True - The vf_port_wwn exists
            False - The vf_port_wwn doesn't exist
        """
        if logfile is None:
            safe, logfile = tempfile.mkstemp()
            cmd_fcinfo = "fcinfo hba-port | grep HBA"
            try:
                output_fcinfo = self.retsend(cmd_fcinfo, timeout=180)
            except error.ReturnException:
                output_fcinfo = "No port recorded"
            with open(logfile, 'r+') as fo:
                fo.write(output_fcinfo)

        cmd = 'grep %s %s' % (port_wwn, logfile)
        try:
            execute(cmd)
        except error.ExecuteException:
            return False
        else:
            return True

    def check_vf_logical_path_status(self, logical_path, logfile=None):
        """
        Purpose:
            Check vf whether the logical_path has exist
        Arguments:
            vf - VF name
            logfile - The log of the "luxadm probe|grep Path"
        Return:
            True - The vf mapping logical_path alive
            False - The vf mapping logical_path does not alive
        """
        if logfile is None:
            safe, logfile = tempfile.mkstemp()
            cmd_luxadm = "luxadm probe|grep Path"
            try:
                output_luxadm = self.retsend(cmd_luxadm, timeout=180)
            except error.ReturnException:
                output_luxadm = "No logical path recorded"
            with open(logfile, 'r+') as fo:
                fo.write(output_luxadm)

        cmd = 'grep %s %s' % (logical_path, logfile)
        try:
            execute(cmd)
        except error.ExecuteException:
            return False
        else:
            return True

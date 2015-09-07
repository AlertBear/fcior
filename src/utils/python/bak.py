import commands
import time
import shutil
import re

def info_print(string):
    print "INFO : %s" % string


def warn_print(string):
    print "WARN : %s" % string


def error_print(string):
    print "ERROR: %s" % string


def execute(cmd):
    (status, output) = commands.getstatusoutput(cmd)
    if status != 0:
        raise Exception(
            "Execution of [%s] failed:\n%s" %
            (cmd, output))
    return output


def remove_vf_from_domain(vf, domain):
    """
    Purpose:
        Remove vf from ldom
    Arguments:
        vf - The specified vf to remove
        domain - The specified domain to remove from
    Return:
        None
    """
    cmd = 'ldm rm-io %s %s' % (vf, domain)
    execute(cmd)


def destroy_all_vfs_on_pf(pf):
    """
    Purpose:
        Destroy all the vfs that pf has created
    Arguments:
        pf - The pf where to destroy vfs
    Return:
        None
    """
    vfs_list = list_all_vfs_on_pf(pf)
    for vf in vfs_list:
        cmd = 'ldm list-io -l -p %s|grep %s' % (pf, vf)
        output = execute(cmd)
        # The vf has been bound to a domain,need to be removed
        domain = output.split('|')[4].split('=')[1]
        if domain != '':
            try:
                remove_vf_from_domain(vf, domain)
            except Exception as e:
                raise e
            else:
                time.sleep(3)

    # Destroy all the vfs created under the pf
    cmd_destroy = 'ldm destroy-vf -n max %s' % pf
    execute(cmd_destroy)


def list_all_vfs_on_pf(pf):
    """
    Purpose:
        List all vfs that pf has created
    Arguments:
        pf - PF name
    Return:
        vfs_list - All vfs that pf has created
    """
    cmd = 'ldm list-io | grep %s' % pf
    output = execute(cmd)
    pattern = re.compile(r'{0}\.VF\d+'.format(pf))
    match = pattern.findall(output)
    if match is None:
        return None
    vfs_list = match
    return vfs_list


def delete_path(path):
    """
    Purpose:
        Remove the directory
    Arguments:
        path - The directory to remove
    Return:
        None
    """
    if os.path.exists(path):
        shutil.rmtree(path)
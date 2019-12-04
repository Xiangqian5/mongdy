#!/usr/bin/env python
# -*- encoding: utf-8 -*-

from __future__ import absolute_import, division, print_function, with_statement

import subprocess
import shlex
import os,sys
import logging

def execCommands(cmds):
    args = []
    proc = []
    cnt  = len(cmds)
    for i in range(cnt):
        command_line = shlex.split(cmds[i])
        args.append(command_line)
        if i == 0:
            proc.append(subprocess.Popen(args[i], stdout=subprocess.PIPE))
        else:
            proc.append(subprocess.Popen(args[i], stdin=proc[i-1].stdout, stdout=subprocess.PIPE))
    
    out = proc[cnt-1].communicate()
    for i in range(cnt):
        proc[i].wait()

    logging.log(logging.INFO, out[0])
    return "".join(out[0])

def execCommandLine(command_line, pipe = "||"):
    try:
        cmds = command_line.split(pipe)
        return execCommands(cmds)
    except Exception as e:
        logging.log(logging.DEBUG, "CommandLine error: %s", e)
        return
    
if __name__ == "__main__":
    execCommandLine("ls -l || grep tcp || grep rel")

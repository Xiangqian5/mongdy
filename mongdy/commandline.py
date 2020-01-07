#!/usr/bin/env python
# -*- encoding: utf-8 -*-

from __future__ import absolute_import, division, print_function, with_statement

import subprocess
import shlex
import os,sys
import logging
import re

class CommandLines():
    def __init__(self, command_in):
        self._command_in = self._strip_blank(command_in)
        self._seq_list = []
        self._out_ = []

    def _strip_blank(self, command_in):
        strinfo = re.compile(' +')
        command_line = strinfo.sub(' ', command_in)
        return command_line

    def _parse_command_line(self):
        try:
            command_line = self._command_in

            word = []
            words = []
            _command_lines = []
            _pipe_lines = []
            quot = 0
            pipe = 0
            for i in range(len(command_line)):
                if command_line[i] in ["'", '"'] and quot == 0:
                    quot = 1
                elif command_line[i] in ["'", '"'] and quot == 1:
                    quot = 0

                if i == len(command_line) - 1:
                    word.append(command_line[i])
                    words.append(''.join(word))
                    if pipe == 1:
                        _pipe_lines.append(' '.join(words))
                        self._seq_list.append(_pipe_lines)
                        _pipe_lines = []
                    else:
                        _command_lines.append(' '.join(words))
                        self._seq_list.append(_command_lines)
                        _command_lines = []
                    word = []
                    words = []
                    pipe = 0
                elif command_line[i] == '|' and quot == 0:
                    _pipe_lines.append(' '.join(words))
                    words = []
                    pipe = 1
                elif command_line[i] == ' ' and quot == 0:
                    words.append(''.join(word))
                    word = []
                elif command_line[i] == ";" and quot == 0:
                    words.append(''.join(word))
                    if pipe == 1:
                        _pipe_lines.append(' '.join(words))
                        self._seq_list.append(_pipe_lines)
                        _pipe_lines = []
                    else:
                        _command_lines.append(' '.join(words))
                        self._seq_list.append(_command_lines)
                        _command_lines = []
                    words = []
                    word = []
                    pipe = 0
                else:
                    word.append(command_line[i])
        except Exception as e:
            import traceback
            logging.log(logging.DEBUG, "CommandLine error: %s", e)
            traceback.print_exc()
            return

    def _exec_command(self, cmds, cwd):
        args = []
        proc = []
        cnt  = len(cmds)
        for i in range(cnt):
            command_line = shlex.split(cmds[i])
            args.append(command_line)
            if i == 0:
                proc.append(subprocess.Popen(args[i], stdout=subprocess.PIPE, cwd=cwd))
            else:
                proc.append(subprocess.Popen(args[i], stdin=proc[i-1].stdout, stdout=subprocess.PIPE, cwd=cwd))
        
        out = proc[cnt-1].communicate()
        for i in range(cnt):
            proc[i].wait()

        ret = out[0].decode('utf-8')

        self._out_.append(ret)

    def exec_command_lines(self):
        try:
            self._parse_command_line()
            cwd = os.getcwd()
            for cmds in self._seq_list:
                if cmds[0][:3] == 'cd ':
                    cwd = cmds[0][3:]
                self._exec_command(cmds, cwd)
        except Exception as e:
            print(e)
            return str(e)

        return ''.join(self._out_)

        
if __name__ == "__main__":
    cmd = CommandLines("ls -l | grep \"py;;|\" | sort -n | uniq -c;pwd;ls -l | grep | ssd ;pwd")
    cmd = CommandLines("cd /data1;ls;cd -;pwd")
    out = cmd.exec_command_lines()
    print(out)

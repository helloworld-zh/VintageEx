import sublime
import sublime_plugin

import os
import subprocess
import ctypes

import ex_range


def gather_buffer_info(v):
    """gathers data to be displayed by :ls or :buffers
    """
    path = v.file_name()
    if path:
        parent, leaf = os.path.split(path)
        parent = os.path.basename(parent)
        path = os.path.join(parent, leaf)
    else:
        path = v.name() or str(v.buffer_id())
        leaf = v.name() or 'untitled'

    status = [] 
    if not v.file_name():
        status.append("t")
    if v.is_dirty():
        status.append("*")
    if v.is_read_only():
        status.append("r")
    
    if status:
        leaf += ' (%s)' % ', '.join(status)
    return [leaf, path]


def get_buffer_range(view, text_range):
    a, b = ex_range.calculate_range(view, text_range)
    r = sublime.Region(view.text_point(a - 1, 0),
                        view.line(
                            view.text_point(b - 1, 0)).end())    
    return r


def get_oem_cp():
    codepage = ctypes.windll.kernel32.GetOEMCP()
    return str(codepage)


def get_startup_info():
    # Hide the child process window.
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    return startupinfo


class ExGoto(sublime_plugin.TextCommand):
    def run(self, edit, range='', **kwargs):
        assert range, 'Range required.'
        a, b = ex_range.calculate_range(self.view, range, is_only_range=True)
        target = (max(a, b) if all((a, b)) else (a or b)) or 0
        self.view.run_command('vi_goto_line', {'repeat': target})


class ExShellOut(sublime_plugin.TextCommand):
    def run(self, edit, args='', **kwargs):
        sels = self.view.sel()
        if all([(s.a != s.b) for s in sels]):
            if os.name == 'nt':
                for s in self.view.sel():
                    p = subprocess.Popen(
                                        ['cmd.exe', '/C', args],
                                        stdout=subprocess.PIPE,
                                        startupinfo=get_startup_info()
                                        )
                    cp = 'cp' + get_oem_cp()
                    rv = p.communicate()[0].decode(cp)[:-2].strip()
                    self.view.replace(edit, s, rv)
                return
            elif os.name == 'posix':
                for s in self.view.sel():
                    shell = os.path.expandvars("$SHELL")
                    p = subprocess.Popen([shell, '-c', args],
                                                        stdout=subprocess.PIPE)
                    self.view.replace(edit, s, p.communicate()[0])
                return
        elif os.name == 'posix':
            term = os.path.expandvars("$COLORTERM") or \
                                                    os.path.expandvars("$TERM")
            subprocess.Popen([term, '-e',
                    "bash -c \"%s; read -p 'Press RETURN to exit.'\"" %
                                                                args]).wait()
            return
        elif os.name == 'nt':
            subprocess.Popen(['cmd.exe', '/c', args + '&& pause']).wait()
            return 

        sublime.status_message('VintageEx: Not implemented.')


class ExReadShellOut(sublime_plugin.TextCommand):
    def run(self, edit, shell_cmd='', forced=False, **kwargs):
        # xxx fix this stuff. pass all arguments in a tidy manner
        if '_extra' in kwargs:
            shell_cmd += ' ' + kwargs['_extra']
        if os.name == 'posix':
            if forced:
                shell = os.path.expandvars("$SHELL")
                p = subprocess.Popen([shell, '-c', shell_cmd],
                                                    stdout=subprocess.PIPE)
                self.view.insert(edit, self.view.sel()[0].begin(),
                                                            p.communicate()[0])
        elif os.name == 'nt':
            if forced:
                p = subprocess.Popen(
                                    ['cmd.exe', '/C', shell_cmd],
                                    stdout=subprocess.PIPE,
                                    startupinfo=get_startup_info()
                                    )
                cp = 'cp' + get_oem_cp()
                rv = p.communicate()[0].decode(cp)[:-2].strip()
                self.view.insert(edit, self.view.sel()[0].begin(), rv)
        else:
            sublime.status_message('VintageEx: Not implemented.')


class ExPromptSelectOpenFile(sublime_plugin.TextCommand):
    def run(self, edit, **kwargs):
        self.file_names = [gather_buffer_info(v)
                                        for v in self.view.window().views()]
        self.view.window().show_quick_panel(self.file_names, self.on_done)

    def on_done(self, idx):
        if idx == -1: return
        # focus the file chosen
        sought_fname = self.file_names[idx]
        for v in self.view.window().views():
            if v.file_name() and v.file_name().endswith(sought_fname[1]):
                self.view.window().focus_view(v)
            # xxx probably all checks should be based on the buffer id
            elif v.buffer_id() == int(sought_fname[1]):
                self.view.window().focus_view(v)


class ExMap(sublime_plugin.TextCommand):
    # do at least something moderately useful: open the user's .sublime-keymap
    # file
    def run(self, edit, **kwargs):
        if os.name == 'nt':
            plat = 'Windows'
        elif os.name == 'posix':
            plat = 'Linux'
        else:
            plat = 'OSX'
        self.view.window().run_command('open_file', {'file':
                                        '${packages}/User/Default (%s).sublime-keymap' % plat})        


class ExAbbreviate(sublime_plugin.TextCommand):
    # for them moment, just open a completions file.
    def run(self, edit, **kwargs):
        abbreviations_file = os.path.join(
                                    sublime.packages_path(),
                                    'User/Vintage Abbreviations.sublime-completions'
                                    )
        if not os.path.exists(abbreviations_file):
            with open(abbreviations_file, 'w'):
                pass
        
        self.view.window().run_command('open_file', {'file': abbreviations_file})


class ExPrintWorkingDir(sublime_plugin.TextCommand):
    def run(self, edit, **kwargs):
        sublime.status_message(os.getcwd())


class ExWriteFile(sublime_plugin.TextCommand):
    def run(self, edit, file_name='', range=None, forced=False,
            plusplus_args='', plus_args='', args='', cmd_arg='', **kwargs):
        appending = file_name == '>>'
        if appending: file_name = kwargs['args_extra']

        if range:
            r = get_buffer_range(self.view, range)
            if file_name and file_name != os.path.basename(
                                                        self.view.file_name()):
                if appending:
                    # xxx open with codecs and append to the file
                    pass
                else:
                    v = self.view.window().new_file()
                    v.set_name(file_name)
                    v_edit = v.begin_edit()
                    v.insert(v_edit, 0, self.view.substr(r))
                    v.end_edit(v_edit)
            elif appending:
                    self.view.insert(edit, self.view.size(),
                                                    '\n' + self.view.substr(r))
            else:
                text = self.view.substr(r) 
                self.view.insert(edit, 0, text)
                self.view.replace(edit, sublime.Region(len(text), 
                                            self.view.size()), '')
            return

        if file_name and file_name != os.path.basename(self.view.file_name()):
            # xxx we should probably save right away
            v = self.view.window().new_file()
            v.insert(edit, 0, self.view.substr(
                                        sublime.Region(0, self.view.size())))
            v.set_name(file_name)
            return
        
        if appending:
            content = self.view.substr(sublime.Region(0, self.view.size()))
            self.view.insert(edit, self.view.size(), '\n' + content)
        
        if self.view.is_dirty():
            self.view.run_command('save')


class ExWriteAll(sublime_plugin.TextCommand):
    def run(self, edit, **kwargs):
        for v in self.view.window().views():
            if v.is_dirty():
                v.run_command('save')


class ExNewFile(sublime_plugin.TextCommand):
    def run(self, edit, **kwargs):
        self.view.window().run_command('new_file')

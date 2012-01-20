#!/usr/bin/env python
# encoding: utf-8
# Jérôme Carretero, 2012 (zougloub)

from waflib import Configure, Options, Utils, Task, TaskGen
from waflib.Tools import c, ccroot, c_preproc
from waflib.Configure import conf
from waflib.TaskGen import feature, before_method, taskgen_method

import os, re

opj = os.path.join

@conf
def find_ticc(conf):
	cc = conf.find_program(['cl6x'], var='CC', path_list=opj(getattr(Options.options, 'ti-cgt-dir', ""), 'bin'))
	cc = conf.cmd_to_list(cc)
	conf.env.CC_NAME = 'ticc'
	conf.env.CC = cc

@conf
def find_tild(conf):
	ld = conf.find_program(['lnk6x'], var='LINK_CC', path_list=opj(getattr(Options.options, 'ti-cgt-dir', ""), 'bin'))
	ld = conf.cmd_to_list(ld)
	conf.env.LINK_CC_NAME = 'tild'
	conf.env.LINK_CC = ld

@conf
def find_tiar(conf):
	ar = conf.find_program(['ar6x'], var='AR', path_list=opj(getattr(Options.options, 'ti-cgt-dir', ""), 'bin'))
	ar = conf.cmd_to_list(ar)
	conf.env.AR = ar
	conf.env.AR_NAME = 'tiar'
	conf.env.ARFLAGS = 'rcs'

@conf
def ticc_common_flags(conf):
	v = conf.env

	if not v['LINK_CC']: v['LINK_CC'] = v['CC']
	v['CCLNK_SRC_F']	 = []
	v['CCLNK_TGT_F']	 = ['-o']
	v['CPPPATH_ST']	  = '-I%s'
	v['DEFINES_ST']	  = '-d%s'

	v['LIB_ST']	      = '-l%s' # template for adding libs
	v['LIBPATH_ST']	  = '-i%s' # template for adding libpaths
	v['STLIB_ST']	    = '-l%s'
	v['STLIBPATH_ST']	= '-i%s'

	# program
	v['cprogram_PATTERN']    = '%s.out'

	# static lib
	#v['LINKFLAGS_cstlib']    = ['-Wl,-Bstatic']
	v['cstlib_PATTERN']      = 'lib%s.a'

def configure(conf):
	v = conf.env
	v.TI_CGT_DIR = getattr(Options.options, 'ti-cgt-dir', "")
	v.TI_DSPLINK_DIR = getattr(Options.options, 'ti-dsplink-dir', "")
	v.TI_BIOSUTILS_DIR = getattr(Options.options, 'ti-biosutils-dir', "")
	v.TI_DSPBIOS_DIR = getattr(Options.options, 'ti-dspbios-dir', "")
	v.TI_XDCTOOLS_DIR = getattr(Options.options, 'ti-xdctools-dir', "")
	conf.find_ticc()
	conf.find_tiar()
	conf.find_tild()
	conf.ticc_common_flags()
	conf.cc_load_tools()
	conf.cc_add_flags()
	conf.link_add_flags()
	v.TCONF = conf.cmd_to_list(conf.find_program(['tconf'], var='TCONF', path_list=v.TI_XDCTOOLS_DIR))
	
	conf.env.TCONF_INCLUDES += [
	 opj(conf.env.TI_DSPBIOS_DIR, 'packages'),
	]
	
	conf.env.INCLUDES += [
	 opj(conf.env.TI_CGT_DIR, 'include'),
	]
	
	conf.env.LIBPATH += [
	 opj(conf.env.TI_CGT_DIR, "lib"),
	]

	conf.env.LINKFLAGS += []

	conf.env.INCLUDES_DSPBIOS += [
	 opj(conf.env.TI_DSPBIOS_DIR, 'packages', 'ti', 'bios', 'include'),
	]
	
	conf.env.LIBPATH_DSPBIOS += [
	 opj(conf.env.TI_DSPBIOS_DIR, 'packages', 'ti', 'bios', 'lib'),
	]

	conf.env.INCLUDES_DSPLINK += [
	 opj(conf.env.TI_DSPLINK_DIR, 'dsplink', 'dsp', 'inc'),
	]
	
@conf
def ti_set_debug(cfg, debug=1):
	if debug:
		cfg.env.CFLAGS += "-d_DEBUG -dDEBUG".split()
		# TODO for each TI CFLAG/INCLUDES/LINKFLAGS/LIBPATH replace RELEASE by DEBUG

@conf
def ti_dsplink_set_platform_flags(cfg, splat, dsp, dspbios_ver, board):
	"""
	Sets the INCLUDES, LINKFLAGS for DSPLINK and TCONF_INCLUDES
	For the specific hardware.

	Assumes that DSPLINK was built in its own folder.

	:param splat: short platform name (eg. OMAPL138)
	:param dsp: DSP name (eg. 674X)
	:param dspbios_ver: string identifying DspBios version (eg. 5.XX)
	:param board: board name (eg. OMAPL138GEM)

	"""
	d = opj(cfg.env.TI_DSPLINK_DIR, 'dsplink', 'dsp', 'inc', 'DspBios', dspbios_ver, board)
	cfg.env.TCONF_INCLUDES += [d]
	cfg.env.INCLUDES_DSPLINK += [
	 opj(cfg.env.TI_DSPLINK_DIR, 'dsplink', 'dsp', 'inc', dsp),
	 d,
	]
	
	cfg.env.LINKFLAGS_DSPLINK += [
	 opj(cfg.env.TI_DSPLINK_DIR, 'dsplink', 'dsp', 'export', 'BIN', 'DspBios', splat, board+'_0', 'RELEASE', 'dsplink%s.lib' % x)
	 for x in ['', 'pool', 'mpcs', 'mplist', 'msg', 'data', 'notify', 'ringio']
	]


re_tconf_include = re.compile(r'(?P<type>utils\.importFile)\("(?P<file>.*)"\)',re.M)
class ti_tconf(Task.Task):
	run_str = '${TCONF} ${TCONFINC} ${TCONFPROGNAME} ${TCONFSRC} ${PROCID}'
	color   = 'PINK'

	def scan(self):
		node = self.inputs[0]
		includes = Utils.to_list(getattr(self, 'includes', []))
		nodes, names = [], []
		if node:
			code = Utils.readf(node.abspath())
			for match in re_tconf_include.finditer(code):
				path = match.group('file')
				if path:
					for x in includes:
						filename = opj(x, path)
						fi = self.path.find_resource(filename)
						if fi:
							nodes.append(fi)
							names.append(path)
							break

		return (nodes, names)

@feature("ti-tconf")
@before_method('process_source')
def apply_tconf(self):
	sources = [x.get_src() for x in self.to_nodes(self.source, path=self.path.get_src())]
	node = sources[0]
	assert(sources[0].name.endswith(".tcf"))
	if len(sources) > 1:
		assert(sources[1].name.endswith(".cmd"))

	target = getattr(self, 'target', self.source)
	target_node = node.get_bld().parent.find_or_declare(node.name)
	
	procid = "%d" % int(getattr(self, 'procid', 0))

	importpaths = []
	includes = Utils.to_list(getattr(self, 'includes', []))
	for x in includes + self.env.TCONF_INCLUDES:
		if x == os.path.abspath(x):
			importpaths.append(x)
		else:
			relpath = self.path.find_node(x).path_from(target_node.parent)
			importpaths.append(relpath)

	task = self.create_task('ti_tconf', sources, target_node.change_ext('.cdb'))
	task.path = self.path
	task.includes = includes
	task.cwd = target_node.parent.abspath()
	task.env = self.env
	task.env["TCONFSRC"] = node.path_from(target_node.parent)
	task.env["TCONFINC"] = '-Dconfig.importPath=%s' % ";".join(importpaths)
	task.env['TCONFPROGNAME'] = '-Dconfig.programName=%s' % target
	task.env['PROCID'] = procid
	task.outputs = [
	 target_node.change_ext("cfg_c.c"),
	 target_node.change_ext("cfg.s62"),
	 target_node.change_ext("cfg.cmd"),
	]

	s62task = create_compiled_task(self, 'c', task.outputs[1])
	ctask = create_compiled_task(self, 'c', task.outputs[0])
	ctask.env.LINKFLAGS += [target_node.change_ext("cfg.cmd").abspath()]
	if len(sources) > 1:
		ctask.env.LINKFLAGS += [sources[1].bldpath()]

	self.source = []

def options(opt):
	opt.add_option('--with-ti-cgt', type='string', dest='ti-cgt-dir', help = 'Specify alternate cgt root folder', default="")
	opt.add_option('--with-ti-biosutils', type='string', dest='ti-biosutils-dir', help = 'Specify alternate biosutils folder', default="")
	opt.add_option('--with-ti-dspbios', type='string', dest='ti-dspbios-dir', help = 'Specify alternate dspbios folder', default="")
	opt.add_option('--with-ti-dsplink', type='string', dest='ti-dsplink-dir', help = 'Specify alternate dsplink folder', default="")
	opt.add_option('--with-ti-xdctools', type='string', dest='ti-xdctools-dir', help = 'Specify alternate xdctools folder', default="")

@taskgen_method
def create_compiled_task(self, name, node):
	out = '%s' % (node.change_ext('.obj').name)
	task = self.create_task(name, node, node.parent.find_or_declare(out))
	self.env.OUT = '-fr%s' % (node.parent.get_bld().abspath())
	try:
		self.compiled_tasks.append(task)
	except AttributeError:
		self.compiled_tasks = [task]
	return task

ccroot.create_compiled_task = create_compiled_task

def hack():
	t = Task.classes['c']
	t.run_str = '${CC} ${ARCH_ST:ARCH} ${CFLAGS} ${CPPFLAGS} ${FRAMEWORKPATH_ST:FRAMEWORKPATH} ${CPPPATH_ST:INCPATHS} ${DEFINES_ST:DEFINES} ${SRC} -c ${OUT}'
	(f,dvars) = Task.compile_fun(t.run_str, t.shell)
	t.hcode = t.run_str
	t.run = f
	t.vars.extend(dvars)

	t = Task.classes['cprogram']
	t.run_str = '${LINK_CC} ${LIBPATH_ST:LIBPATH} ${LIB_ST:LIB} ${LINKFLAGS} ${CCLNK_SRC_F}${SRC} ${CCLNK_TGT_F}${TGT[0].bldpath()} ${RPATH_ST:RPATH} ${FRAMEWORKPATH_ST:FRAMEWORKPATH} ${FRAMEWORK_ST:FRAMEWORK} ${ARCH_ST:ARCH} ${STLIB_MARKER} ${STLIBPATH_ST:STLIBPATH} ${STLIB_ST:STLIB} ${SHLIB_MARKER} '
	(f,dvars) = Task.compile_fun(t.run_str, t.shell)
	t.hcode = t.run_str
	t.run = f
	t.vars.extend(dvars)

hack()


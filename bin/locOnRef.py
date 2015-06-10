
#
#  Copyright 2014 CIRAD
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, see <http://www.gnu.org/licenses/> or
#  write to the Free Software Foundation, Inc.,
#  51 Franklin Street, Fifth Floor, Boston,
#  MA 02110-1301, USA.
#
#


import optparse, os, shutil, subprocess, sys, tempfile, fileinput, ConfigParser, operator, time, multiprocessing
from Bio.Seq import Seq
from Bio.Alphabet import generic_dna
from Bio import SeqIO
from Bio.SeqRecord import SeqRecord

def stop_err( msg ):
    sys.stderr.write( "%s\n" % msg )
    sys.exit()

def run_job (cmd_line, ERROR):
	print cmd_line
	try:
		tmp = tempfile.NamedTemporaryFile().name
		# print tmp
		error = open(tmp, 'w')
		proc = subprocess.Popen( args=cmd_line, shell=True, stderr=error)
		returncode = proc.wait()
		error.close()
		error = open( tmp, 'rb' )
		stderr = ''
		buffsize = 1048576
		try:
			while True:
				stderr += error.read( buffsize )
				if not stderr or len( stderr ) % buffsize != 0:
					break
		except OverflowError:
			pass
		error.close()
		os.remove(tmp)
		if returncode != 0:
			raise Exception, stderr
	except Exception, e:
		stop_err( ERROR + str( e ) )


def __main__():
	#Parse Command Line
	parser = optparse.OptionParser()
	# Wrapper options. 
	parser.add_option( '', '--ref', dest='ref', default=None, help='The reference fasta file')
	parser.add_option( '', '--blast', dest='blast', default='n', help='Use blast, y or n, [default: %default]')
	parser.add_option( '', '--bwa_mem', dest='bwa_mem', default='n', help='Use bwa_mem, y or n, [default: %default]')
	parser.add_option( '', '--bow', dest='bow', default='n', help='Use bowtie2, y or n, [default: %default]')
	parser.add_option( '', '--bow_loc', dest='bow_loc', default='n', help='Use bowtie2 with local mod, y or n, [default: %default]')
	parser.add_option( '', '--fasta', dest='fasta', default=None, help='The fasta file containing markers')
	parser.add_option( '', '--out', dest='out', default='MarkOnScaff.tab', help='Output file name')
	parser.add_option( '', '--margin', dest='margin', default='2500', help='The margin to consider hit as similar (integer), [default: %default]')
	parser.add_option( '', '--index', dest='index', default='y', help='Build reference index : y or n,  [default: %default]')
	parser.add_option( '', '--rmindex', dest='rmindex', default='y', help='Remove reference index at the end of calculation: y or n, [default: %default]')
	parser.add_option( '', '--thread', dest='thread', default='1', help='The thread number used for mapping (integer). For --blast no more than 5 is required, for --bow 1, for --bow_loc 1, for --bwa_mem 1) [default: %default]')
	(options, args) = parser.parse_args()
	
	
	
	if options.ref == None:
		sys.exit('--ref argument is missing')
	if options.fasta == None:
		sys.exit('--fasta argument is missing')
	
	ScriptPath = os.path.dirname(sys.argv[0])
	
	loca_programs = ConfigParser.RawConfigParser()
	loca_programs.read(ScriptPath+'/loca_programs.conf')
	
	proc = int(options.thread)
	
	# print ('ScriptPath', ScriptPath)
	# print ("output", options.out)
	# print ("input", options.ref)
	
	#Verifying redundancy
	dico = set()
	file = open(options.fasta)
	redundancy = 0
	for line in file:
		data = line.split()
		if data:
			if data[0][0] == '>':
				if data[0][1:] in dico:
					print 'There is redundancy in multifasta names', data[0][1:]
					redundancy = 1
				else:
					dico.add(data[0][1:])
	if redundancy:
		sys.exit('The program ended because it is not able to manage duplicate names of sequence')
	
	liste_job = []
	if options.index == 'y':
		if options.blast == 'y':
			liste_job.append('%s -in %s -dbtype nucl' % (loca_programs.get('Programs','formatdb'), options.ref))
		if options.bwa_mem == 'y':
			liste_job.append('%s index -a bwtsw %s 2>/dev/null' % (loca_programs.get('Programs','bwa'), options.ref))
		if  options.bow == 'y' or options.bow_loc == 'yes':
			liste_job.append('%s --quiet %s %s' % (loca_programs.get('Programs','bowtie2-build'), options.ref, options.ref))
		
		liste_process = []
		for n in liste_job:
			t = multiprocessing.Process(target=run_job, args=(n, 'Bug when indexing',))
			liste_process.append(t)
			if len(liste_process) == proc:
				for process in liste_process:
					process.start()
				for process in liste_process:
					process.join()
				liste_process = []
		if liste_process:
			for process in liste_process:
				process.start()
			for process in liste_process:
				process.join()
			liste_process = []
	
	#Mapping
	liste_job = []
	if options.blast == 'y':
		outblast = options.out+'_blast'
		liste_job.append('%s -query %s -db %s -out %s -evalue 1e-10 -dust no' % (loca_programs.get('Programs','blastall'), options.fasta, options.ref, outblast))
	if options.bwa_mem == 'y':
		outbwa = options.out+'_bwa'
		liste_job.append('%s mem -M %s %s > %s' % (loca_programs.get('Programs','bwa'), options.ref, options.fasta, outbwa))
	if options.bow == 'y':
		outbow = options.out+'_bow'
		liste_job.append('%s --very-sensitive --quiet -x %s -f %s -S %s' % (loca_programs.get('Programs','bowtie2'), options.ref, options.fasta, outbow))
	if options.bow_loc == 'y':
		outbowloc = options.out+'_bowloc'
		liste_job.append('%s --very-sensitive-local --quiet -x %s -f %s -S %s' % (loca_programs.get('Programs','bowtie2'), options.ref, options.fasta, outbowloc))
		
	liste_process = []
	for n in liste_job:
		t = multiprocessing.Process(target=run_job, args=(n, 'Bug when mapping',))
		liste_process.append(t)
		if len(liste_process) == proc:
			for process in liste_process:
				process.start()
			for process in liste_process:
				process.join()
			liste_process = []
	if liste_process:
		for process in liste_process:
			process.start()
		for process in liste_process:
			process.join()
		liste_process = []
		
	if options.rmindex == 'y':
		os.system('rm '+options.ref+'.*')
	
	nom_blast = os.getpid()
	
	# Filtering
	liste_job = []
	if options.blast == 'y':
		out98 = options.out+'_blast98'
		liste_job.append('%s %s/BLAT_gros.py --blast %s --ident 98 --max_hit 2 --seq 10 --out 98%s > %s' % (loca_programs.get('Programs','python'),ScriptPath , outblast, nom_blast, out98))
		out95 = options.out+'_blast95'
		liste_job.append('%s %s/BLAT_gros.py --blast %s --ident 95 --max_hit 2 --seq 10 --out 95%s > %s' % (loca_programs.get('Programs','python'),ScriptPath , outblast, nom_blast, out95))
		out90 = options.out+'_blast90'
		liste_job.append('%s %s/BLAT_gros.py --blast %s --ident 90 --max_hit 2 --seq 10 --out 90%s > %s' % (loca_programs.get('Programs','python'),ScriptPath , outblast, nom_blast, out90))
		out85 = options.out+'_blast85'
		liste_job.append('%s %s/BLAT_gros.py --blast %s --ident 85 --max_hit 2 --seq 10 --out 85%s > %s' % (loca_programs.get('Programs','python'),ScriptPath , outblast, nom_blast, out85))
		out80 = options.out+'_blast80'
		liste_job.append('%s %s/BLAT_gros.py --blast %s --ident 80 --max_hit 2 --seq 10 --out 80%s > %s' % (loca_programs.get('Programs','python'),ScriptPath , outblast, nom_blast, out80))
	if options.bwa_mem == 'y':
		tabbwa = options.out+'_bwa.tab'
		liste_job.append('%s %s/Filter_single_hit_sam.py --sam %s --dif 1 --type tab > %s' % (loca_programs.get('Programs','python'),ScriptPath , outbwa, tabbwa))
	if options.bow == 'y':
		tabbow = options.out+'_bow.tab'
		liste_job.append('%s %s/Filter_single_hit_sam.py --sam %s --dif 1 --type tab > %s' % (loca_programs.get('Programs','python'),ScriptPath , outbow, tabbow))
	if options.bow_loc == 'y':
		tabbowloc = options.out+'_bowloc.tab'
		liste_job.append('%s %s/Filter_single_hit_sam.py --sam %s --dif 1 --type tab > %s' % (loca_programs.get('Programs','python'),ScriptPath , outbowloc, tabbowloc))
		
	liste_process = []
	for n in liste_job:
		t = multiprocessing.Process(target=run_job, args=(n, 'Bug when Filtering',))
		liste_process.append(t)
		if len(liste_process) == proc:
			for process in liste_process:
				process.start()
			for process in liste_process:
				process.join()
			liste_process = []
	if liste_process:
		for process in liste_process:
			process.start()
		for process in liste_process:
			process.join()
		liste_process = []
	
	
	# On enregistre les identifiants des sequences
	record_dict = SeqIO.index(options.fasta, "fasta")
	dico = {}
	for n in record_dict:
		dico[n] = set()
	
	#on cherche les positions
	if options.blast == 'y':
		file = open(out98)
		for line in file:
			data = line.split()
			if data:
				dico[data[0]].add(data[1]+'%'+data[5])
		file.close()
		file = open(out95)
		for line in file:
			data = line.split()
			if data:
				dico[data[0]].add(data[1]+'%'+data[5])
		file.close()
		file = open(out90)
		for line in file:
			data = line.split()
			if data:
				dico[data[0]].add(data[1]+'%'+data[5])
		file.close()
		file = open(out85)
		for line in file:
			data = line.split()
			if data:
				dico[data[0]].add(data[1]+'%'+data[5])
		file.close()
		file = open(out80)
		for line in file:
			data = line.split()
			if data:
				dico[data[0]].add(data[1]+'%'+data[5])
		file.close()
	if options.bwa_mem == 'y':
		file = open(tabbwa)
		for line in file:
			data = line.split()
			if data:
				dico[data[0]].add(data[1]+'%'+data[5])
		file.close()
	if options.bow == 'y':
		file = open(tabbow)
		for line in file:
			data = line.split()
			if data:
				dico[data[0]].add(data[1]+'%'+data[5])
		file.close()
	if options.bow_loc == 'y':
		file = open(tabbowloc)
		for line in file:
			data = line.split()
			if data:
				dico[data[0]].add(data[1]+'%'+data[5])
		file.close()
	
	#On identifie les hits uniques
	dico_group = {}
	for n in dico:
		if len(dico[n]) == 1:
			# outfile.write(n+'\t'+'\t'.join(list(dico[n])[0].split('%'))+'\n')
			chr =list(dico[n])[0].split('%')[0]
			pos = int(list(dico[n])[0].split('%')[1])
			if chr in dico_group:
				dico_group[chr].append([n,pos])
			else:
				dico_group[chr] = []
				dico_group[chr].append([n,pos])
		elif len(dico[n]) > 1:
			proches = 1
			chr_ref = ''
			pos_ref = ''
			for j in dico[n]:
				if chr_ref == '':
					chr_ref = j.split('%')[0]
					pos_ref = int(j.split('%')[1])
					pos_deb = pos_ref - int(options.margin)
					pos_fin = pos_ref + int(options.margin)
				else:
					chr = j.split('%')[0]
					pos = int(j.split('%')[1])
					if chr != chr_ref or pos < pos_deb or pos > pos_fin:
						proches = 0
			if proches == 1:
				# outfile.write(n+'\t'+chr_ref+'\t'+str(pos_ref)+'\n')
				if chr_ref in dico_group:
					dico_group[chr_ref].append([n,pos_ref])
				else:
					dico_group[chr_ref] = []
					dico_group[chr_ref].append([n,pos_ref])
			else:
				mot = n
				for j in dico[n]:
					mot = mot + '\t' + '\t'.join(j.split('%'))
				print mot
		else:
			print n
	
	outfile = open(options.out,'w')
	for n in dico_group:
		liste = []
		liste = sorted(dico_group[n],key=operator.itemgetter(1))
		for j in liste:
			outfile.write(j[0]+'\t'+n+'\t'+str(j[1])+'\n')
	outfile.close()
	
	if options.blast == 'y':
		os.remove(out98)
		os.remove(out95)
		os.remove(out90)
		os.remove(out85)
		os.remove(out80)
		os.remove(outblast)
	if options.bwa_mem == 'y':
		os.remove(outbwa)
		os.remove(tabbwa)
	if options.bow == 'y':
		os.remove(outbow)
		os.remove(tabbow)
	if options.bow_loc == 'y':
		os.remove(outbowloc)
		os.remove(tabbowloc)

if __name__ == "__main__": __main__()
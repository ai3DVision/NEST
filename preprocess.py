import os
import json
import numpy as np
from subprocess import call
from main import FLAGS
from Predictor import Graph


class Meta(object):
	def __init__(self, perm):
		self.perm = perm

	def match(self, ns):
		ns = np.array(ns)
		return ns[self.perm]

	@staticmethod
	def read_meta(file):
		def read_one(f):
			if f.readline() == '':
				return None
			f.readline()
			line = np.array(map(int, f.readline().rstrip().split()[1:]))
			meta = np.concatenate(np.split(line, len(line) / 2)[::2], axis=0)
			f.readline()
			f.readline()
			f.readline()
			return meta

		metas = []
		with open(file, 'r') as f:
			while True:
				meta = read_one(f)
				if meta == None:
					break
				metas.append(Meta(meta))
		return metas


class Preprocess(object):
	def __init__(self, params=FLAGS):
		self.params = params
		self.graph = Graph(params)
		self.train_cas = self.read_cascade(self.params.data_dir + 'train/' + self.params.train)
		self.test_cas = self.read_cascade(self.params.data_dir + 'test/' + self.params.test)


	def read_cascade(self, path):
		cascade = []
		with open(path, 'r') as f:
			for line in f:
				src, rest = line.strip().split(' ', 1)
				cascade.append([int(src)] + map(int, rest.split()[::2][:-1]))
		return cascade

	def create_subgraph(self, cascade, mode):
		path = self.params.data_dir + mode + '/' + self.params.subgraph
		if not os.path.exists(path):
			os.makedirs(path)
		for i, cas in enumerate(cascade):
			self.write_subg(cas, path, i)

	def write_subg(self, ns, path, id):
		ns = sorted(ns)
		es = self.graph.subgraph_es(ns)
		with open(path + 'g' + str(id), 'w') as f:
			f.write('t #\n')
			for n in ns:
				f.write('v %d 0\n' % n)
			for e in es:
				f.write('e %d %d 0\n' % (e[0], e[1]))

	def create_kernel(self):
		kernels = json.load(open(self.params.data_dir + self.params.kernel))
		self.num_kernel = len(kernels)
		with open(self.params.data_dir + self.params.query, 'w') as f:
			for _, val in sorted(kernels.iteritems()):
				f.write('t #\n')
				for i in xrange(val['v']):
					f.write('v %d 0\n' % i)
				for e in val['e']:
					f.write('e %d %d 0\n' % (e[0], e[1]))
					f.write('e %d %d 0\n' % (e[1], e[0]))
				for i in xrange(val['v']):
					f.write('a %d\n' % i)

	def match(self, mode):
		call('cp %s SubMatch/%s' % (self.params.data_dir + self.params.query, self.params.query), shell=True)
		call('rm -rf SubMatch/output/', shell=True)
		dir = self.params.data_dir + mode + '/'
		for file in os.listdir(dir + self.params.subgraph):
			if file == '.DS_Store':
				continue
			os.makedirs('SubMatch/output/%s' % file)
			call('cp %s SubMatch/data/' % (dir + self.params.subgraph + file), shell=True)
			real_to_fake, fake_to_real, run = self.rewrite_input('SubMatch/data/%s' % file)
			if run:
				command = 'wine SubMatch/SubMatch.exe mode=2 data=SubMatch/data/%s query=SubMatch/%s maxfreq=100 stats=SubMatch/output/%s' % \
						  (file, self.params.query, file)
				call(command, shell=True)
				self.rewrite_output('SubMatch/output/%s/' % file, fake_to_real)
			self.merge(mode, file)
		call('rm SubMatch/data/g*; rm result; rm SubMatch/%s' % self.params.query, shell=True)
		call('rm subgraphs; rm -rf SubMatch/output/', shell=True)


	def merge(self, mode, dir):
		meta_dir = self.params.data_dir + mode + '/' + self.params.meta
		if not os.path.exists(meta_dir):
			os.makedirs(meta_dir)
		metas = Meta.read_meta('subgraphs')
		with open(meta_dir + dir, 'w') as fw:
			for i in xrange(self.num_kernel):
				fw.write('#\t%d\n' % (i + 1))
				file = 'SubMatch/output/' + dir + '/' + str(i + 1)
				if not os.path.exists(file):
					continue
				with open(file, 'r') as fr:
					for line in fr:
						line = line.rstrip().split()
						fw.write('\t'.join(metas[i].match(line)) + '\n')


	def rewrite_input(self, file):
		real_to_fake, fake_to_real = {}, {}
		es = []
		fake_id = 0
		with open(file, 'r') as f:
			next(f)
			for line in f:
				line = line.rstrip().split()
				if line[0] == 'v':
					real_to_fake[int(line[1])] = fake_id
					fake_to_real[fake_id] = int(line[1])
					fake_id += 1
				else:
					es.append((real_to_fake[int(line[1])], real_to_fake[int(line[2])]))
		with open(file, 'w') as f:
			f.write('t #\n')
			for n in range(fake_id):
				f.write('v %d 0\n' % n)
			for e in es:
				f.write('e %d %d 0\n' % (e[0], e[1]))
		return real_to_fake, fake_to_real, len(es) > 0

	def rewrite_output(self, dir, fake_to_real):
		for file in os.listdir(dir):
			ns = []
			with open(dir + file, 'r') as f:
				for line in f:
					ns.append(map(int, line.rstrip().split()))
			with open(dir + file, 'w') as f:
				for n in ns:
					f.write('\t'.join(map(lambda x : str(fake_to_real[x]), n)) + '\n')


if __name__ == '__main__':
	preproc = Preprocess()
	preproc.create_subgraph(preproc.train_cas, mode='train')
	preproc.create_subgraph(preproc.test_cas, mode='test')
	preproc.create_kernel()
	preproc.match('train')
	preproc.match('test')
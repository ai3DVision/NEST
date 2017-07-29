from NN import *

class GCN(object):
	def __init__(self, params):
		self.params = params
		self.build()

	def build(self):
		self.embedding = embedding('embedding', [self.params.num_node, self.params.node_dim])
		'''
		placeholder can only take one subgraph to avoid multiple None dimensions
		tensorflow will throw exception when sub-dimensions does not match
		however, every subgraph can have different number of kernels
		therefore cannot pad null tensor otherwise would be bad for average pooling
		'''
		self.kernel = [tf.placeholder(tf.int32, [None, size]) for size in self.params.kernel_sizes]

		if self.params.task == 'cascade':
			self.candidate = tf.placeholder(tf.int32, [None])
			# the entry of ground truth, not index
			self.next = tf.placeholder(tf.int32, shape={})
		else:
			self.label = tf.placeholder(tf.int32, shape=())

		instance_embed = [tf.reshape(tf.nn.embedding_lookup(self.embedding, self.kernel[i]), [-1, self.params.kernel_sizes[i] * self.params.node_dim])
		                       for i in range(self.params.num_kernel)]
		assert len(self.params.instance_h_dim) == len(self.params.instance_activation)
		for h, dim, activation in zip(range(len(self.params.instance_h_dim)), self.params.instance_h_dim, self.params.instance_activation):
			instance_embed = [fully_connected(instance_embed[i], dim, 'Conv_' + str(i) + str(h), activation=activation)
							  for i in range(self.params.num_kernel)]

		pooling = {'max': (lambda embed: tf.reduce_max(embed, axis=0)),
				   'average': (lambda embed: tf.reduce_mean(embed, axis=0)),
				   'sum': (lambda embed: tf.reduce_sum(embed, axis=0))}
		kernel_embed = [pooling[self.params.pooling](embed) for embed in instance_embed]
		graph_embed = tf.expand_dims(tf.concat(kernel_embed, axis=0), dim=0)

		assert len(self.params.graph_h_dim) == len(self.params.graph_activation)
		for h, dim, activation in zip(range(len(self.params.graph_h_dim)), self.params.graph_h_dim, self.params.graph_activation):
			graph_embed = fully_connected(graph_embed, dim, 'FC_' + str(h), activation=activation)

		if self.params.task == 'cascade':
			candidate_embed = tf.nn.embedding_lookup(self.embedding, self.candidate)
			logits = tf.transpose(tf.matmul(candidate_embed, tf.transpose(graph_embed)))
		else:
			logits = fully_connected(graph_embed, self.params.num_label, 'logits', activation=None)

		if self.params.task == 'cascade':
			loss = tf.nn.sparse_softmax_cross_entropy_with_logits(labels=tf.expand_dims(self.next, dim=0), logits=logits)
		else:
			loss = tf.nn.sparse_softmax_cross_entropy_with_logits(labels=tf.expand_dims(self.label, dim=0), logits=logits)

		self.predict = tf.cast(tf.argmax(logits, 1), 'int32')

		if self.params.task == 'cascade':
			self.top_k = tf.nn.top_k(logits, k=self.params.k, sorted=True)

		global_step = tf.Variable(0, trainable=False)
		learning_rate = tf.train.inverse_time_decay(self.params.learning_rate, global_step, 1, self.params.decay_rate)

		optimizer = tf.train.AdamOptimizer(learning_rate=learning_rate)
		self.gradient_descent = optimizer.minimize(loss, global_step=global_step)

		for variable in tf.trainable_variables():
			print(variable.name, variable.get_shape())

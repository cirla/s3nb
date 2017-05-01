SSH=vagrant ssh

CONFIG_DIR=config
CONFIG_FILE=${CONFIG_DIR}/jupyter_notebook_config.py

AWS_USER=s3nb

.PHONY=clean configure creds kill restart run

clean:
	rm -rf clean/ credentials

configure:
	if [ -r ${CONFIG_FILE} ]; then mv ${CONFIG_FILE} ${CONFIG_FILE}.orig; else mkdir -p ${CONFIG_DIR}; touch ${CONFIG_FILE}; fi
	echo "c = get_config()" >> ${CONFIG_FILE}
	echo "c.NotebookApp.log_level = 'DEBUG'" >> ${CONFIG_FILE}
	echo "c.NotebookApp.contents_manager_class = 's3nb.S3ContentsManager'" >> ${CONFIG_FILE}
	echo "c.S3ContentsManager.base_uri = '${S3_BASE_URI}'" >> ${CONFIG_FILE}
	echo "c.S3ContentsManager.checkpoints_kwargs = {'root_dir': '/vagrant/.checkpoints'}" >> ${CONFIG_FILE}

creds:
	grep -A2 ${AWS_USER} ~/.aws/credentials | sed 's/${AWS_USER}/default/g' > credentials
	${SSH} -c "mkdir -p ~/.aws && ln -sf /vagrant/credentials ~/.aws/credentials"

kill:
	${SSH} -c "tmux kill-session -t server || true"

restart: kill run;

run:
	${SSH} -c "tmux new-session -d -n run -s server 'PYTHONPATH=/vagrant jupyter notebook --config=/vagrant/${CONFIG_FILE} --ip=0.0.0.0 --no-browser > /vagrant/s3nb.log 2>&1'"

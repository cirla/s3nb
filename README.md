# S3-backed notebook manager for IPython

## Setup

1. Install:

    from pypi:
    ```bash
    pip install s3nb
    ```

    from source with pip:
    ```bash
    pip install git+https://github.com/monetate/s3nb
    ```

    or from source the old fashioned way:
    ```bash
    git clone git@github.com:monetate/s3nb.git
    cd s3nb
    python ./setup.py install
    ```

2. Configure

    ``` bash
    # set this - notebooks will be stored relative to this uri
    S3_NOTEBOOK_URI=s3://path/to/notebooks/

    # optionally set this - checkpoints will be stored locally, relative to this path
    CHECKPOINT_ROOT_DIR=~/.checkpoints

    JUPYTER_CONFIG_DIR=${JUPYTER_CONFIG_DIR:-$HOME/.jupyter_config}
    JUPYTER_CONFIG=${JUPYTER_DIR}/jupyter_notebook_config.py

    mv $JUPYTER_CONFIG $JUPYTER_CONFIG.orig
    cat > $JUPYTER_CONFIG <<EOF
    c = get_config()
    c.NotebookApp.contents_manager_class = 's3nb.S3ContentsManager'
    c.S3ContentsManager.base_uri = '$S3_NOTEBOOK_URI'
    c.S3ContentsManager.checkpoints_kwargs = {'root_dir': '${CHECKPOINT_ROOT_DIR}'}
    EOF

    ```

3. If you haven't already, configure AWS variables for boto.  [Follow these instructions](http://blogs.aws.amazon.com/security/post/Tx3D6U6WSFGOK2H/A-New-and-Standardized-Way-to-Manage-Credentials-in-the-AWS-SDKs).

4. Run
    ``` bash
    jupyter notebook --config=~/.ipython/s3nbserver/ipython_notebook_config.py
    ```

## Development

1. Provision a virtual machine with `vagrant up`
2. Create an IPython profile with `make configure -e S3_BASE_URI=YOUR_BUCKET`
4. Share you AWS credentials with the virtual machine with `make creds -e AWS_USER=YOUR_USER`
4. Run the notebook server with `make run`

# Das Lab Website Server

<img src="https://daslab.stanford.edu/site_media/images/logo_das.png" alt="DasLab Logo" align="right" width="200" />

This is the _Source Code_ repository for **DasLab** Website **Server**. The production server is freely accessible at https://daslab.stanford.edu/.

## Installation

**DasLab Server** requires the following *Python* packages as dependencies, most of which can be installed through [`pip`](https://pip.pypa.io/).

```json
boto >= 2.48.0
Django >= 1.11.7
django-adminplus >= 0.5
django-crontab >= 0.7.1
django-environ >= 0.4.4
django-filemanager == 0.0.2
django-suit >= 0.2.25
django-widget-tweaks >= 1.4.1
dropbox >= 8.6.0
gviz-api.py == 1.8.2
icalendar >= 4.0.0
MySQL-python >= 1.2.5
PyGithub >= 1.35
pytz >= 2017.3
requests >= 2.18.4
simplejson >= 3.13.2
slacker >= 0.9.60
```

The `gviz-api.py` is available at [`google-visualization-python`](https://github.com/google/google-visualization-python/).

The `django-filemanager` is a modified version of [`django-filemanager`](https://github.com/IMGIITRoorkee/django-filemanager/). The source code is available internally at this [fork](https://github.com/t47io/django-filemanager/).

Install with:

```sh
cd ~
git clone https://github.com/google/google-visualization-python.git
cd google-visualization-python
sudo python setup.py install

cd ..
git clone https://github.com/t47io/django-filemanager.git
cd django-filemanager
sudo python setup.py install
```

**DasLab Server** also requires proper setup of `mysql.server`, `apache2`, `mod_wsgi`, `mod_webauth`, `openssl`, `wallet`, `gdrive`, `pandoc`, `awscli`, and `cron` jobs.

Lastly, assets preparation is required for the 1st time through running `sudo python manage.py versions`, `util_prep_dir.sh`, `util_minify.sh`, `util_chmod.sh` and manually replacing `config/*.conf`. For full configuration, please refer to **Documentation**.


## Usage

To run the test/dev server, use:

```bash
cd path/to/server_daslab/repo
python manage.py runserver
```

The server should be running at `localhost:8000` with a python session interactive in terminal.

## Documentation

- Documentation is available at admin [manual](https://daslab.stanford.edu/admin/man/) and [reference](https://daslab.stanford.edu/admin/ref/).

- Alternatively, read the repository [**Wiki**](https://github.com/DasLab/Server_Daslab/wiki/).

## License

**Copyright &copy; 2015-2018: Siqi Tian _[[t47](https://t47.io/)]_, Das Lab, Stanford University. All Rights Reserved.**

**DasLab Server** _Source Code_ is proprietary and confidential. Unauthorized copying of this repository, via any medium, is strictly prohibited.


by [**t47**](https://t47.io/), *January 2016*.


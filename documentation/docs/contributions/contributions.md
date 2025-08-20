---
hide_table_of_contents: false
---

# Contributions

### 1. Setup documentation locally

```bash
cd documentation
```

Install Node.js packages
```bash
npm install 
````

To start a local development server:

```bash
npm start
```

The documentation will be available at [http://localhost:3000/django-admin-logs-viewer/](http://localhost:3000/django-admin-logs-viewer/).

:::note
Deployment of the documentation and the PyPI package is automatic after merging changes into the `main` branch.
:::

## 2. Setup Python environment

```bash
pip install -r requirements.txt
pip install -e . # To automatically use locally developed django-admin-logs-viewer package
```

## 3. Create Django admin user and run example project

`example_project` is available for testing. To set it up, do:

```bash
cd example_project
```

Apply migrations:
```bash
python manage.py migrate
```

To generate example logs:
```bash
python manage.py generate_logs
```

Create admin account:
```bash
python manage.py createsuperuser
```

Then run the development server:
```bash
python manage.py runserver
```

You can access the admin panel at [http://127.0.0.1:8000/admin](http://127.0.0.1:8000/admin).

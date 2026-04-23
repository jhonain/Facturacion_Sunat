
---

## ⚙️ Instalación y Configuración

### 1. Clonar el repositorio
```bash
git clone https://github.com/jhonain/Facturacion_Sunat.git
cd facturacion-sunat
```

### 2. Configurar variables de entorno
```bash
cp .env.example .env
# Edita el .env con tus credenciales
```

### 3. Levantar con Docker
```bash
docker compose up --build -d
```

### 4. Migraciones
```bash
docker compose exec web python manage.py migrate
```

### 5. Crear superusuario
```bash
docker compose exec web python manage.py createsuperuser
```

### 6. Acceder
- **Admin:** http://localhost:8000/admin/

---
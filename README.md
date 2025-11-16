# Proyecto_Modelado-y-diseño-de-software

Perfecto, ahora vamos a **armar TODA la documentación lista para copiar/pegar** en tu TP, siguiendo EXACTAMENTE lo que pide el profesor en el PDF.

> ⚠ Sin mezclar temas y en el orden solicitado por la consigna.
> ⚠ Todo listo para entregar (texto 100% pulido).
> ⚠ No incluimos nada del código aquí, solo la documentación del sistema.

---

#  **DOCUMENTACIÓN COMPLETA DEL TP**

---

# **1. Glosario de términos del dominio**

### **Usuario**

Persona registrada en el sistema Finanza, identificada de forma única por su email.

### **Actor**

Rol o tipo de usuario que interactúa con el sistema (VisitanteFinanza, UsuarioFinanza, AdministradorFinanzas).

### **Rol**

Conjunto de permisos asignados a un usuario que determina qué acciones puede ejecutar dentro del sistema.

### **Permiso**

Acción puntual que puede realizar un rol (ej.: gestionar usuarios, acceder a reportes, etc.).

### **Sesión**

Período durante el cual un usuario autenticado interactúa con el sistema luego de iniciar sesión.

### **Registrar**

Proceso mediante el cual un VisitanteFinanza crea una nueva cuenta de usuario completando sus datos.

### **Iniciar sesión / Login**

Proceso por el cual un usuario se identifica ingresando su email y contraseña.

### **Token de confirmación**

Identificador único enviado al usuario para activar su cuenta antes de poder iniciar sesión.

### **Estado de cuenta**

Condición del usuario: *pendiente*, *activa*, *bloqueada*.

---

# **2. Actores y sus metas**

### **VisitanteFinanza**

* Registrar una cuenta en el sistema.
* Activar su cuenta mediante token.

### **UsuarioFinanza** (Empleado/Cliente)

* Iniciar sesión.
* Acceder a las funciones básicas del sistema Finanza (según sus permisos).

### **AdministradorFinanzas**

* Gestionar usuarios.
* Asignar y modificar roles.
* Consultar estados de cuenta.
* Garantizar la correcta administración del acceso en Finanza.

*(Opcionales si necesitás sumar puntos)*

### **AnalistaFinanzas / OperadorFinanzas**

* Acceder a reportes o acciones específicas del dominio financiero según su rol.

---

# **3. Historias de Usuario (HU)**

Formato Gherkin / Given-When-Then (opcional pero claro y profesional)

---

## **HU1 – Registrarse en Finanza**

**Como** VisitanteFinanza
**Quiero** registrarme con mi nombre, email y contraseña
**Para** poder obtener una cuenta en el sistema Finanza.

**Criterios de aceptación (G-W-T):**

* **Dado** que el visitante ingresa sus datos completos
* **Cuando** realiza el registro
* **Entonces** el sistema debe guardar el usuario con estado *pendiente*
* **Y** generar un token de confirmación.

---

## **HU2 – Confirmar mi cuenta**

**Como** UsuarioFinanza
**Quiero** activar mi cuenta con un token
**Para** poder iniciar sesión de manera segura.

**Criterios:**

* **Dado** un usuario con estado *pendiente*
* **Cuando** accede al enlace de activación
* **Entonces** su estado pasa a *activa*.

---

## **HU3 – Iniciar sesión**

**Como** UsuarioFinanza
**Quiero** iniciar sesión con mi email y contraseña
**Para** acceder a mis funcionalidades de Finanza.

**Criterios:**

* **Dado** un usuario con estado *activo*
* **Cuando** ingresa credenciales correctas
* **Entonces** accede al sistema.
* **Si** la cuenta no está activa → debe impedir el acceso.

---

## **HU4 – Administrar usuarios y roles**

**Como** AdministradorFinanzas
**Quiero** asignar roles a los usuarios
**Para** controlar qué acciones pueden realizar dentro del sistema.

---

# **4. Casos de Uso (CU)**

Formato estándar UML textual.

---

## **CU1 – Registrarse**

**Actor:** VisitanteFinanza
**Precondición:** No debe existir otro usuario con el mismo email.
**Flujo principal:**

1. El visitante ingresa nombre, email y contraseña.
2. El sistema valida datos.
3. El sistema crea el usuario con estado *pendiente*.
4. El sistema genera un token de confirmación.
5. El sistema informa que se generó la cuenta.

**Flujos alternativos:**

* 2a: Email duplicado → informar error.
* 2b: Contraseñas no coinciden → informar error.

---

## **CU2 – Confirmar cuenta**

**Actor:** UsuarioFinanza
**Precondición:** El usuario debe tener un token válido.

**Flujo principal:**

1. El usuario accede al enlace enviado.
2. El sistema recibe el token.
3. El sistema verifica si el token es válido.
4. Cambia el estado de la cuenta a *activa*.
5. Marca el token como *usado*.

**Excepciones:**

* Token inválido.
* Token expirado.

---

## **CU3 – Iniciar sesión**

**Actor:** UsuarioFinanza
**Precondición:** El usuario debe tener una cuenta *activa*.

**Flujo principal:**

1. El usuario ingresa email y contraseña.
2. El sistema verifica existencia del email.
3. El sistema verifica la contraseña.
4. El sistema crea la sesión de usuario.
5. Se abre la interfaz principal de Finanza.

**Excepciones:**

* Cuenta inactiva.
* Credenciales inválidas.

---

## **CU4 – Administrar usuarios y roles**

**Actor:** AdministradorFinanzas
**Precondición:** Usuario con rol AdministradorFinanzas.

**Flujo principal:**

1. El administrador visualiza la lista de usuarios.
2. Selecciona un usuario.
3. Asigna o modifica roles.
4. Guarda cambios.

**Excepciones:**

* Usuario no encontrado.
* Rol inexistente.

---

# **5. Diagramas UML (para que los dibujes)**

<img width="334" height="531" alt="image" src="https://github.com/user-attachments/assets/547d07e8-4c9f-4dd4-87d8-c5e3c6e453db" />


---

## **5.1. Diagrama de Casos de Uso**

**Actores:**

* VisitanteFinanza
* UsuarioFinanza
* AdministradorFinanzas

**Casos:**

* CU1 Registrarse
* CU2 Confirmar cuenta
* CU3 Iniciar sesión
* CU4 Administrar usuarios y roles

Con líneas:

* VisitanteFinanza → CU1
* UsuarioFinanza → CU2 / CU3
* AdministradorFinanzas → CU4

---

## **5.2. Diagrama de Clases**

Clases obligatorias:

```
Usuario
- id
- nombre
- email
- password_hash
- estado: EstadoCuenta
- roles: List[Rol]
+ verificar_password()
+ tiene_permiso()

Rol
- nombre
- permisos: List[Permiso]

Permiso
- nombre

TokenConfirmacion
- token
- usuario_id
- expiracion
- usado
```

Relaciones:

* Usuario *1..*—0..* Rol
* Rol *1..*—0..* Permiso
* Usuario *1–1* TokenConfirmacion (solo cuando está pendiente)

---

## **5.3. Diagrama de Secuencia (Solicitar acceso y autorizar/denegar)**

*(lo pide el profe aunque no esté implementado)*

Participantes:

```
UsuarioFinanza → GUI Finanza → AuthService → RBACService → Auditoría (opcional)
```

Pasos:

1. Usuario solicita acceso a una sección (“Módulo X”).
2. GUI envía solicitud al AuthService.
3. AuthService consulta RBACService.
4. RBACService verifica los roles del usuario.
5. Devuelve PERMITIDO / DENEGADO.
6. AuthService informa resultado a la GUI.
7. (Opcional) Registra evento en auditoría.
8. La GUI muestra acceso o mensaje de denegado.

---

## **5.4. Diagrama de Actividad (Permitir / Denegar acceso)**

Flujo:

* Inicio
* Usuario autenticado solicita acceso
* Verificar permisos del rol
* [Decisión]

  * Si permitido → permitir acceso
  * Si no → acceso denegado
* Registrar evento (opcional)
* Fin

---

# **6. Tabla de trazabilidad**

| RF   | Caso de Uso           | Clases / Entidades         | Diagramas / GUI                        |
| ---- | --------------------- | -------------------------- | -------------------------------------- |
| RF1  | CU1 Registrarse       | Usuario, TokenConfirmacion | Registro (gui_auth)                    |
| RF2  | CU2 Confirmar cuenta  | TokenConfirmacion, Usuario | Secuencia confirmación                 |
| RF3  | CU3 Iniciar sesión    | Usuario, EstadoCuenta      | Login (gui_auth) + app.gui_mp          |
| RF4  | CU4 Administrar roles | Usuario, Rol, Permiso      | Diagrama de clases / diseño conceptual |
| RF5* | CU5 Solicitar acceso  | Usuario, Rol, Zona         | Secuencia acceso-denegación            |
| RF7* | CU6 Registrar evento  | Auditoría, EventoAcceso    | Diagrama actividad                     |

*Opcionales del profesor.

---
te preparo **los diagramas en formato XML de draw.io** listos para importar. ¿Querés eso?

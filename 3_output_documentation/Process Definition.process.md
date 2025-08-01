# Proceso: Process Definition.process

**Ruta:** `1_tibco_project_source/TIBCO_BW_BE/Process Definition.process`

---

## 1. Resumen Funcional

Este proceso, disparado por un temporizador, envía un evento `EventA` a la cola `NewDestination_0` cada segundo.  El evento contiene un campo `Test1` con el valor de la hora actual obtenida del temporizador.

---

## 2. Disparador (Starter)

*   **Nombre:** `Timer`
*   **Tipo:** `com.tibco.plugin.timer.TimerEventSource`
*   **Configuración:**
    *   Inicio: `1361093595000` (timestamp Unix)
    *   Frecuencia: `true` (indica que es periódico)
    *   Intervalo de tiempo: `1`
    *   Unidad de frecuencia: `Second`


---

## 3. Flujo de Actividades y Datos

El proceso inicia con el temporizador `Timer`, que se activa cada segundo.  Esto dispara la actividad `Send Event`.

**Actividad: Send Event**

*   **Nombre:** `Send Event`
*   **Tipo:** `com.tibco.be.bw.plugin.BESendEvent`
*   **Configuración:**
    *   `rspRef`: `/RuleServiceProvider Configuration.sharedrsp` (Referencia al servicio de reglas)
    *   `eventRef`: `/Events/EventA` (Referencia al esquema del evento)
    *   `entityNS`: `/Events/EventA` (Namespace del evento)
    *   `entityName`: `EventA` (Nombre del evento)
    *   `destinationRef`: `/Channels/JMSChannel/NewDestination_0` (Referencia al destino JMS)
*   **Mapeos de datos de entrada:**
    *   El campo `Test1` se llena con la hora actual del Timer, obtenida a través de la expresión `$Timer/ns:TimerOutputSchema/Time`.


Después de enviar el evento, el proceso finaliza. La transición de "Send Event" a "End" siempre se ejecuta.

---

## 4. Dependencias

*   **Recursos Compartidos:**
    *   `RuleServiceProvider Configuration.sharedrsp`
*   **Esquemas y Eventos:**
    *   `Channels/JMSChannel/NewDestination_0.aeschema`
    *   `Events/EventA.aeschema`
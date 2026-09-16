// google_map.js — Dash carga automáticamente cualquier .js dentro de la
// carpeta /assets/ al arrancar la página. Esta función queda disponible
// como clientside callback en Python: "window.dash_clientside.mapa_google.renderizar"
//
// Usa AdvancedMarkerElement (la versión moderna y liviana de los
// marcadores, recomendada por Google desde 2024) en vez de
// google.maps.Marker (la vieja, más pesada — se nota sobre todo en celu
// con varios cientos de puntos).

window.dash_clientside = Object.assign({}, window.dash_clientside, {
    mapa_google: {
        renderizar: function (data) {
            if (!window.google || !window.google.maps || !window.google.maps.marker) {
                // El script de Google Maps (o la librería "marker") todavía
                // no cargó — reintentamos en un momento.
                setTimeout(function () {
                    window.dash_clientside.mapa_google.renderizar(data);
                }, 300);
                return window.dash_clientside.no_update;
            }

            const contenedor = document.getElementById("mapa_google_container");
            if (!contenedor) {
                return window.dash_clientside.no_update;
            }

            // Limpiar marcadores de la vuelta anterior
            if (window._alomaMapMarkers) {
                window._alomaMapMarkers.forEach(function (m) { m.map = null; });
            }
            window._alomaMapMarkers = [];

            const puntos = data || [];
            const centro = puntos.length > 0
                ? { lat: puntos[0].lat, lng: puntos[0].lng }
                : { lat: -32.9468, lng: -60.6393 }; // Rosario, fallback si no hay datos

            if (!window._alomaMap) {
                window._alomaMap = new google.maps.Map(contenedor, {
                    center: centro,
                    zoom: 12,
                    // AdvancedMarkerElement necesita un Map ID (puede ser
                    // el de demo de Google, sirve igual sin configurar nada).
                    mapId: "DEMO_MAP_ID",
                });
            } else if (puntos.length > 0) {
                window._alomaMap.setCenter(centro);
            }

            if (!window._alomaInfoWindow) {
                window._alomaInfoWindow = new google.maps.InfoWindow();
            }

            const { AdvancedMarkerElement } = google.maps.marker;

            puntos.forEach(function (punto) {
                // Un puntito circular simple con CSS, en vez del ícono SVG
                // más pesado que usaba el Marker viejo.
                const pin = document.createElement("div");
                pin.style.width = "14px";
                pin.style.height = "14px";
                pin.style.borderRadius = "50%";
                pin.style.backgroundColor = punto.color || "#3b82f6";
                pin.style.border = "2px solid #ffffff";
                pin.style.boxShadow = "0 1px 3px rgba(0,0,0,0.45)";

                const marker = new AdvancedMarkerElement({
                    position: { lat: punto.lat, lng: punto.lng },
                    map: window._alomaMap,
                    title: punto.title || "",
                    content: pin,
                });

                marker.addListener("click", function () {
                    window._alomaInfoWindow.setContent(punto.info || punto.title || "");
                    window._alomaInfoWindow.open(window._alomaMap, marker);
                });
                window._alomaMapMarkers.push(marker);
            });

            return "";
        }
    }
});
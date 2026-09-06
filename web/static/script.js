async function updateScale() {

    try {

        const response = await fetch("/api/status");

        if (!response.ok) {
            throw new Error("Kunde inte läsa status");
        }

        const data = await response.json();

        document.getElementById("weight").textContent =
            data.weight_g.toFixed(1) + " g";

        document.getElementById("timestamp").textContent =
            data.timestamp;

    } catch (error) {

        console.error(error);

        document.getElementById("weight").textContent = "--- g";

        document.getElementById("timestamp").textContent =
            "Ingen kontakt";
    }
}


async function tareScale() {

    const button = document.getElementById("tare-button");
    const message = document.getElementById("message");

    button.disabled = true;
    message.textContent = "Tarerar vågen...";

    try {

        const response = await fetch("/api/tare", {
            method: "POST"
        });

        if (!response.ok) {
            throw new Error("Tarering misslyckades");
        }

        message.textContent = "Vågen tareras...";

        setTimeout(() => {
            message.textContent = "";
        }, 2000);

    } catch (error) {

        console.error(error);
        message.textContent = "Kunde inte tarera vågen";

    } finally {

        button.disabled = false;
    }
}


updateScale();

setInterval(updateScale, 500);
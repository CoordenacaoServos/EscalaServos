// static/script.js
document.addEventListener('DOMContentLoaded', () => {

    let scheduleData = [];
    const scheduleContainer = document.getElementById('schedule-container');

    async function loadScheduleFromAPI() {
        try {
            const response = await fetch('/api/missas');
            if (!response.ok) {
                throw new Error(`Erro na API: ${response.statusText}`);
            }
            const data = await response.json();
            scheduleData = data.status === 'sucesso' ? data.missas : [];
            renderSchedule();
        } catch (error) {
            console.error("Falha ao carregar dados da escala:", error);
            scheduleContainer.innerHTML = '<p style="color:red; text-align:center;">Erro ao carregar a escala. Verifique o console.</p>';
        }
    }

    function renderSchedule() {
        scheduleData.sort((a, b) => new Date(`${a.date}T${a.time}`) - new Date(`${b.date}T${b.time}`));
        scheduleContainer.innerHTML = '';
        if (scheduleData.length === 0) {
            scheduleContainer.innerHTML = '<p style="text-align:center; color:#888;">Nenhuma missa encontrada.</p>';
            return;
        }
        scheduleData.forEach(mass => {
            const massCard = document.createElement('div');
            massCard.className = 'mass-card';
            const [year, month, day] = mass.date.split('-');
            const formattedDate = `${day}/${month}/${year}`;
            let slotsHTML = '';
            mass.slots.forEach((slot, index) => {
                const isAvailable = slot.acolyte === null;
                const statusClass = isAvailable ? 'available' : 'taken';
                const acolyteInfoHTML = isAvailable ? '<span class="acolyte">Vaga Aberta!</span>' : `<span class="acolyte">${slot.acolyte}</span>`;
                const cancelBtnHTML = isAvailable ? '' : `<span class="cancel-btn" data-mass-id="${mass.id}" data-slot-index="${index}" title="Liberar Vaga">&times;</span>`;
                slotsHTML += `
                    <li class="slot ${statusClass}" data-mass-id="${mass.id}" data-slot-index="${index}">
                        <div class="role-info"><span class="role">${slot.role}</span>${acolyteInfoHTML}</div>
                        ${cancelBtnHTML}
                    </li>`;
            });
            massCard.innerHTML = `<h3>${mass.day} - ${mass.time}</h3><p class="mass-date">${formattedDate}</p><ul class="slots-list">${slotsHTML}</ul>`;
            scheduleContainer.appendChild(massCard);
        });
    }

    scheduleContainer.addEventListener('click', (event) => {
        const clickedSlot = event.target.closest('.slot.available');
        if (clickedSlot) {
            // Lógica para pegar vaga (ainda não conectada ao backend)
            const userName = prompt("Digite seu nome para assumir esta função (função de teste):");
            if (userName) alert(`Olá ${userName}! A função de se escalar será conectada ao banco de dados em breve.`);
            return;
        }
        const clickedCancel = event.target.closest('.cancel-btn');
        if (clickedCancel) {
            // Lógica para liberar vaga (ainda não conectada ao backend)
            if (confirm("Tem certeza que deseja liberar esta vaga? (função de teste)")) alert('A função de liberar vaga será conectada ao banco de dados em breve.');
        }
    });

    loadScheduleFromAPI();
});
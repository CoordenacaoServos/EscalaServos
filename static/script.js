// static/script.js (VERSÃO ATUALIZADA)

document.addEventListener('DOMContentLoaded', () => {
    const scheduleContainer = document.getElementById('schedule-container');
    const flashContainer = document.getElementById('flash-container');

    // Função para mostrar mensagens (como o flash do Flask) na tela
    function showFlashMessage(message, category = 'success') {
        if (!flashContainer) return;

        const article = document.createElement('article');
        article.textContent = message;
        // Adiciona uma classe para estilização, se necessário (ex: success, danger)
        if (category === 'danger') {
            article.style.backgroundColor = 'var(--pico-color-red-200)';
            article.style.borderColor = 'var(--pico-color-red-600)';
        }

        flashContainer.innerHTML = ''; // Limpa mensagens antigas
        flashContainer.appendChild(article);

        // Remove a mensagem após 5 segundos
        setTimeout(() => {
            article.style.transition = 'opacity 0.5s';
            article.style.opacity = '0';
            setTimeout(() => article.remove(), 500);
        }, 5000);
    }

    // Função para carregar os dados da escala via API
    async function loadScheduleFromAPI() {
        try {
            const response = await fetch('/api/missas');
            if (!response.ok) {
                throw new Error(`Erro na API: ${response.statusText}`);
            }
            const data = await response.json();
            const scheduleData = data.status === 'sucesso' ? data.missas : [];
            renderSchedule(scheduleData);
        } catch (error) {
            console.error("Falha ao carregar dados da escala:", error);
            scheduleContainer.innerHTML = '<article><p style="color:red; text-align:center;">Erro ao carregar a escala.</p></article>';
        }
    }

    // Função para renderizar a escala na página
    function renderSchedule(scheduleData) {
        scheduleContainer.innerHTML = '';
        if (scheduleData.length === 0) {
            scheduleContainer.innerHTML = '<article><p>Nenhuma missa encontrada.</p></article>';
            return;
        }

        // Agrupa as missas por data para uma melhor visualização
        const missasPorData = scheduleData.reduce((acc, missa) => {
            const dataFormatada = `${missa.day} - ${missa.date.split('-').reverse().join('/')}`;
            if (!acc[dataFormatada]) {
                acc[dataFormatada] = [];
            }
            acc[dataFormatada].push(missa);
            return acc;
        }, {});

        for (const data in missasPorData) {
            const dayCard = document.createElement('article');
            let dayHTML = `<h3>${data}</h3>`;

            missasPorData[data].sort((a, b) => a.time.localeCompare(b.time)); // Ordena missas pelo horário

            missasPorData[data].forEach(mass => {
                let slotsHTML = '';
                mass.slots.forEach(slot => {
                    const isAvailable = slot.acolyte === null;
                    const statusClass = isAvailable ? 'available' : 'taken';
                    const acolyteInfoHTML = isAvailable ? '<span class="acolyte">Vaga Aberta!</span>' : `<span class="acolyte">${slot.acolyte}</span>`;
                    
                    // Lógica corrigida: Mostra o botão 'X' apenas se a vaga pertencer ao usuário logado ('is_mine' vem da API)
                    const cancelBtnHTML = slot.is_mine ? `<span class="cancel-btn" data-vaga-id="${slot.vaga_id}" title="Pedir Substituição">&times;</span>` : '';

                    slotsHTML += `
                        <li class="slot ${statusClass}" data-vaga-id="${slot.vaga_id}" title="${isAvailable ? 'Clique para se inscrever' : ''}">
                            <div class="role-info">
                                <span class="role">${slot.role}</span>
                                ${acolyteInfoHTML}
                            </div>
                            ${cancelBtnHTML}
                        </li>`;
                });
                dayHTML += `<div class="horario-group"><h4>${mass.time}</h4><ul class="slots-list">${slotsHTML}</ul></div><hr>`;
            });

            dayCard.innerHTML = dayHTML.slice(0, -4); // Remove o último <hr>
            scheduleContainer.appendChild(dayCard);
        }
    }

    // Função para PEDIR SUBSTITUIÇÃO (chama o backend)
    async function releaseSlot(vagaId) {
        if (!confirm('Tem certeza que deseja liberar esta vaga e notificar o grupo?')) {
            return;
        }
        try {
            const response = await fetch(`/pedir-substituicao/${vagaId}`, { method: 'POST' });
            if (!response.ok) throw new Error('Falha na resposta do servidor.');
            // Recarrega a escala para mostrar a mudança
            loadScheduleFromAPI();
            showFlashMessage('Vaga liberada e grupo notificado com sucesso!', 'success');
        } catch (error) {
            console.error('Erro ao liberar vaga:', error);
            showFlashMessage('Ocorreu um erro ao tentar liberar a vaga.', 'danger');
        }
    }

    // Função para SE INSCREVER EM UMA VAGA (chama o backend)
    async function takeSlot(vagaId) {
        if (!confirm('Deseja se inscrever para esta função?')) {
            return;
        }
        try {
            // ATENÇÃO: A rota /api/inscrever-vaga/<vaga_id> precisa ser criada no app.py
            const response = await fetch(`/api/inscrever-vaga/${vagaId}`, { method: 'POST' });
            const data = await response.json();

            if (!response.ok || data.status !== 'sucesso') {
                throw new Error(data.message || 'Não foi possível se inscrever na vaga.');
            }
            // Recarrega a escala para mostrar seu nome na vaga
            loadScheduleFromAPI();
            showFlashMessage(data.message, 'success');
        } catch (error) {
            console.error('Erro ao se inscrever na vaga:', error);
            showFlashMessage(error.message, 'danger');
        }
    }

    // Listener de eventos principal para a escala
    scheduleContainer.addEventListener('click', (event) => {
        const clickedCancel = event.target.closest('.cancel-btn');
        const clickedAvailableSlot = event.target.closest('.slot.available');

        if (clickedCancel) {
            const vagaId = clickedCancel.dataset.vagaId;
            if (vagaId) releaseSlot(vagaId);
            return;
        }
        
        if (clickedAvailableSlot) {
            const vagaId = clickedAvailableSlot.dataset.vagaId;
            if (vagaId) takeSlot(vagaId);
        }
    });

    // Carrega a escala inicial ao abrir a página
    loadScheduleFromAPI();
});
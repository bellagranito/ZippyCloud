document.addEventListener('DOMContentLoaded', () => {
  const root = document.documentElement;

  // Tema claro/escuro
  const applyTheme = (theme) => {
    root.dataset.theme = theme;
    localStorage.setItem('zippy-theme', theme);
    document.querySelectorAll('#theme-toggle').forEach((button) => {
      button.setAttribute('aria-pressed', String(theme === 'dark'));
      button.title = theme === 'dark' ? 'Usar tema claro' : 'Usar tema escuro';
    });
  };

  document.querySelectorAll('#theme-toggle').forEach((button) => {
    button.addEventListener('click', () => {
      applyTheme(root.dataset.theme === 'dark' ? 'light' : 'dark');
    });
  });

  // Menu lateral recolhível
  const drawer = document.querySelector('#app-drawer');
  const overlay = document.querySelector('#drawer-overlay');
  const menuToggle = document.querySelector('#menu-toggle');
  const drawerClose = document.querySelector('#drawer-close');

  const openDrawer = () => {
    if (!drawer || !overlay) return;
    drawer.classList.add('open');
    overlay.hidden = false;
    requestAnimationFrame(() => overlay.classList.add('visible'));
    drawer.setAttribute('aria-hidden', 'false');
    menuToggle?.setAttribute('aria-expanded', 'true');
    document.body.classList.add('drawer-open');
  };

  const closeDrawer = () => {
    if (!drawer || !overlay) return;
    drawer.classList.remove('open');
    overlay.classList.remove('visible');
    drawer.setAttribute('aria-hidden', 'true');
    menuToggle?.setAttribute('aria-expanded', 'false');
    document.body.classList.remove('drawer-open');
    window.setTimeout(() => {
      if (!overlay.classList.contains('visible')) overlay.hidden = true;
    }, 220);
  };

  menuToggle?.addEventListener('click', openDrawer);
  drawerClose?.addEventListener('click', closeDrawer);
  overlay?.addEventListener('click', closeDrawer);
  drawer?.querySelectorAll('a').forEach((link) => link.addEventListener('click', closeDrawer));

  // Painel de notificações
  const notificationToggle = document.querySelector('#notification-toggle');
  const notificationPopover = document.querySelector('#notification-popover');

  const closeNotifications = () => {
    if (!notificationPopover) return;
    notificationPopover.hidden = true;
    notificationToggle?.setAttribute('aria-expanded', 'false');
  };

  notificationToggle?.addEventListener('click', (event) => {
    event.stopPropagation();
    if (!notificationPopover) return;
    const willOpen = notificationPopover.hidden;
    notificationPopover.hidden = !willOpen;
    notificationToggle.setAttribute('aria-expanded', String(willOpen));
  });

  notificationPopover?.addEventListener('click', (event) => event.stopPropagation());
  document.addEventListener('click', closeNotifications);

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') {
      closeDrawer();
      closeNotifications();
    }
  });

  // Máscaras de CPF, telefone e CEP
  const formatarCPF = (valor) => {
    const numeros = valor.replace(/\D/g, '').slice(0, 11);
    if (numeros.length <= 3) return numeros;
    if (numeros.length <= 6) return `${numeros.slice(0, 3)}.${numeros.slice(3)}`;
    if (numeros.length <= 9) return `${numeros.slice(0, 3)}.${numeros.slice(3, 6)}.${numeros.slice(6)}`;
    return `${numeros.slice(0, 3)}.${numeros.slice(3, 6)}.${numeros.slice(6, 9)}-${numeros.slice(9)}`;
  };

  const formatarTelefone = (valor) => {
    const numeros = valor.replace(/\D/g, '').slice(0, 11);
    if (!numeros.length) return '';
    if (numeros.length <= 2) return `(${numeros}`;
    if (numeros.length <= 6) return `(${numeros.slice(0, 2)}) ${numeros.slice(2)}`;
    if (numeros.length <= 10) return `(${numeros.slice(0, 2)}) ${numeros.slice(2, 6)}-${numeros.slice(6)}`;
    return `(${numeros.slice(0, 2)}) ${numeros.slice(2, 7)}-${numeros.slice(7)}`;
  };

  const formatarCEP = (valor) => {
    const numeros = valor.replace(/\D/g, '').slice(0, 8);
    if (numeros.length <= 5) return numeros;
    return `${numeros.slice(0, 5)}-${numeros.slice(5)}`;
  };

  document.querySelectorAll('.cpf-field').forEach((field) => {
    field.value = formatarCPF(field.value);
    field.addEventListener('input', () => { field.value = formatarCPF(field.value); });
  });

  document.querySelectorAll('.telefone-field').forEach((field) => {
    field.value = formatarTelefone(field.value);
    field.addEventListener('input', () => { field.value = formatarTelefone(field.value); });
  });

  // CEP + ViaCEP
  document.querySelectorAll('.cep-field').forEach((field) => {
    field.value = formatarCEP(field.value);
    field.addEventListener('input', () => { field.value = formatarCEP(field.value); });

    field.addEventListener('blur', async () => {
      const cep = field.value.replace(/\D/g, '');
      const form = field.closest('form');
      const endereco = form?.querySelector('.endereco-field');
      if (!endereco || cep.length !== 8) return;

      try {
        const response = await fetch(`https://viacep.com.br/ws/${cep}/json/`);
        const data = await response.json();
        if (data.erro) {
          field.classList.add('invalid');
          alert('CEP inválido.');
          return;
        }
        field.classList.remove('invalid');
        endereco.value = [data.logradouro, data.bairro, data.localidade, data.uf]
          .filter(Boolean)
          .join(', ');
      } catch (_) {
        console.warn('ViaCEP indisponível. O cadastro pode continuar manualmente.');
      }
    });
  });

  // Mostrar/ocultar senha em formulários públicos
  document.querySelectorAll('[data-password-toggle]').forEach((button) => {
    button.addEventListener('click', () => {
      const input = document.getElementById(button.dataset.passwordToggle);
      if (!input) return;
      const hidden = input.type === 'password';
      input.type = hidden ? 'text' : 'password';
      button.textContent = hidden ? '◌' : '◉';
      button.setAttribute('aria-label', hidden ? 'Ocultar senha' : 'Mostrar senha');
    });
  });

  // Cupons disponíveis no PDV conforme o cliente selecionado
  const clienteSelect = document.querySelector('#cliente-select');
  const cupomSelect = document.querySelector('#cupom-select');
  if (clienteSelect && cupomSelect) {
    clienteSelect.addEventListener('change', async () => {
      cupomSelect.innerHTML = '<option value="">Sem cupom</option>';
      if (!clienteSelect.value) return;

      try {
        const response = await fetch(`/api/clientes/${clienteSelect.value}/cupons`);
        const data = await response.json();
        data.cupons.forEach((cupom) => {
          const option = document.createElement('option');
          option.value = cupom.id;
          option.textContent = `${cupom.codigo} — ${cupom.desconto}%`;
          cupomSelect.appendChild(option);
        });
      } catch (_) {
        console.warn('Não foi possível carregar os cupons do cliente.');
      }
    });
  }
});

const CACHE_NAME = 'gestao-turmas-v1';

// Arquivos para cachear — permitem carregar mais rápido
const urlsToCache = [
  '/',
  '/login',
  '/static/manifest.json'
];

// Instala o service worker e faz cache dos arquivos
self.addEventListener('install', function(event) {
  event.waitUntil(
    caches.open(CACHE_NAME).then(function(cache) {
      return cache.addAll(urlsToCache);
    })
  );
});

// Intercepta requisições — usa cache quando disponível
self.addEventListener('fetch', function(event) {
  event.respondWith(
    caches.match(event.request).then(function(response) {
      // Se encontrou no cache retorna o cache
      // Se não, busca na rede normalmente
      return response || fetch(event.request);
    })
  );
});

// Remove caches antigos quando atualizar o service worker
self.addEventListener('activate', function(event) {
  event.waitUntil(
    caches.keys().then(function(cacheNames) {
      return Promise.all(
        cacheNames.filter(function(name) {
          return name !== CACHE_NAME;
        }).map(function(name) {
          return caches.delete(name);
        })
      );
    })
  );
});
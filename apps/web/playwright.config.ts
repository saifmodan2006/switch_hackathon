import {defineConfig,devices} from '@playwright/test';
export default defineConfig({
 testDir:'./tests',fullyParallel:false,workers:1,timeout:45000,
 use:{baseURL:'http://127.0.0.1:3011',trace:'retain-on-failure'},
 webServer:{command:'node ../../scripts/e2e-server.mjs',url:'http://127.0.0.1:3011',reuseExistingServer:false,timeout:120000},
 projects:[{name:'chromium',use:{...devices['Desktop Chrome'],viewport:{width:1440,height:1100}}}]
});

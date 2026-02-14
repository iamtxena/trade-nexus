// @ts-check

const config = {
  title: 'Trade Nexus Docs',
  tagline: 'Contract-first platform documentation portal',
  url: 'https://trade-nexus.local',
  baseUrl: '/',
  onBrokenLinks: 'throw',
  onBrokenMarkdownLinks: 'throw',

  presets: [
    [
      'classic',
      {
        docs: {
          path: '../portal',
          routeBasePath: '/',
          sidebarPath: require.resolve('./sidebars.js')
        },
        blog: false,
        pages: false,
        theme: {
          customCss: require.resolve('./src/css/custom.css')
        }
      }
    ]
  ],

  themeConfig: {
    navbar: {
      title: 'Trade Nexus Docs',
      items: [
        {
          type: 'docSidebar',
          sidebarId: 'docsSidebar',
          position: 'left',
          label: 'Portal'
        },
        {
          href: '/api/platform-api.html',
          label: 'API Reference',
          position: 'right'
        }
      ]
    }
  }
};

module.exports = config;

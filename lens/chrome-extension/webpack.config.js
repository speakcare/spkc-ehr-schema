const path = require('path');
const HtmlWebpackPlugin = require('html-webpack-plugin');
const CopyWebpackPlugin = require('copy-webpack-plugin');

module.exports = {
  mode: 'development',
  entry: {
    panel: path.resolve(__dirname, 'src/panel/index.tsx'),
    background: path.resolve(__dirname, 'src/background/background.ts'),
    content: path.resolve(__dirname, 'src/content/content_script.ts'),
  },
  output: {
    path: path.resolve(__dirname, 'dist'),
    filename: '[name].bundle.js', // Generates panel.bundle.js, background.bundle.js, content.bundle.js
  },
  resolve: {
    extensions: ['.ts', '.tsx', '.js'],
  },
  module: {
    rules: [
      {
        test: /\.(ts|tsx)$/,
        use: 'ts-loader',
        exclude: /node_modules/,
      },
      {
        test: /\.css$/,
        use: ['style-loader', 'css-loader'],
      },
    ],
  },
  plugins: [
    new HtmlWebpackPlugin({
      template: 'public/panel.html',
      filename: 'panel.html',
      chunks: ['panel'], // Use the React panel entry point
    }),
    new CopyWebpackPlugin({
      patterns: [
        { from: 'public/manifest.json', to: '.' }, // Copy manifest.json
        { from: 'public/icons', to: 'icons' },    // Copy icons if any
      ],
    }),
  ],
};

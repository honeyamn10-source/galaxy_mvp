import React, { useEffect, useRef } from 'react';
import * as THREE from 'three';

const COLOR_MAP = {
  fire: 0xff5b5b,
  intrusion: 0xb366ff,
  motion: 0x3aa0ff,
  smoke: 0xffc84d,
};

export default function GalaxyView({ events }) {
  const mountRef = useRef(null);

  useEffect(() => {
    const mount = mountRef.current;
    if (!mount) {
      return undefined;
    }

    const width = mount.clientWidth || 720;
    const height = 420;

    const scene = new THREE.Scene();
    scene.fog = new THREE.Fog(0x08111f, 12, 30);

    const camera = new THREE.PerspectiveCamera(60, width / height, 0.1, 1000);
    camera.position.z = 12;

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));

    mount.innerHTML = '';
    mount.appendChild(renderer.domElement);

    const ambient = new THREE.AmbientLight(0xffffff, 0.8);
    scene.add(ambient);

    const pointLight = new THREE.PointLight(0x66d9ff, 2.2, 80);
    pointLight.position.set(6, 8, 10);
    scene.add(pointLight);

    const backgroundStars = new THREE.BufferGeometry();
    const starPositions = [];
    for (let index = 0; index < 200; index += 1) {
      starPositions.push((Math.random() - 0.5) * 60);
      starPositions.push((Math.random() - 0.5) * 60);
      starPositions.push((Math.random() - 0.5) * 60);
    }
    backgroundStars.setAttribute('position', new THREE.Float32BufferAttribute(starPositions, 3));
    const starMaterial = new THREE.PointsMaterial({ color: 0xffffff, size: 0.07 });
    const starField = new THREE.Points(backgroundStars, starMaterial);
    scene.add(starField);

    const nodes = [];
    const createNode = (event, index) => {
      const geometry = new THREE.SphereGeometry(0.28 + ((index % 3) * 0.05), 18, 18);
      const material = new THREE.MeshStandardMaterial({
        color: COLOR_MAP[event.event_type] || 0xffffff,
        emissive: COLOR_MAP[event.event_type] || 0x111111,
        emissiveIntensity: 0.25,
        metalness: 0.12,
        roughness: 0.35,
      });
      const mesh = new THREE.Mesh(geometry, material);
      const radius = 3.8 + Math.random() * 2.6;
      const angle = (index / Math.max(events.length, 1)) * Math.PI * 2;
      mesh.position.set(
        Math.cos(angle) * radius,
        (Math.random() - 0.5) * 4,
        Math.sin(angle) * radius
      );
      nodes.push(mesh);
      scene.add(mesh);
    };

    events.slice(0, 36).forEach(createNode);

    const coreGeometry = new THREE.SphereGeometry(1.25, 32, 32);
    const coreMaterial = new THREE.MeshStandardMaterial({
      color: 0x8ab4ff,
      emissive: 0x2563eb,
      emissiveIntensity: 0.55,
      metalness: 0.22,
      roughness: 0.3,
    });
    const core = new THREE.Mesh(coreGeometry, coreMaterial);
    scene.add(core);

    let frame = 0;
    const animate = () => {
      frame = requestAnimationFrame(animate);
      core.rotation.x += 0.007;
      core.rotation.y += 0.01;
      starField.rotation.y += 0.0008;
      nodes.forEach((node, index) => {
        node.rotation.x += 0.008 + (index % 4) * 0.001;
        node.rotation.y += 0.01;
        node.position.y += Math.sin(Date.now() * 0.001 + index) * 0.0005;
      });
      renderer.render(scene, camera);
    };
    animate();

    const onResize = () => {
      const nextWidth = mount.clientWidth || width;
      renderer.setSize(nextWidth, height);
      camera.aspect = nextWidth / height;
      camera.updateProjectionMatrix();
    };

    window.addEventListener('resize', onResize);

    return () => {
      window.removeEventListener('resize', onResize);
      cancelAnimationFrame(frame);
      scene.traverse((object) => {
        if (object.geometry) {
          object.geometry.dispose();
        }
        if (object.material) {
          object.material.dispose();
        }
      });
      renderer.dispose();
      mount.innerHTML = '';
    };
  }, [events]);

  return <div className="galaxy-view" ref={mountRef} />;
}
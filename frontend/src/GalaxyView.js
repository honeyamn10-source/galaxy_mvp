import React, { useEffect, useMemo, useRef } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls';

const COLOR_MAP = {
  fire: 0xff5b5b,
  intrusion: 0xb366ff,
  motion: 0x3aa0ff,
  smoke: 0xffc84d,
};

const MAX_RENDER_EVENTS = 80;

export default function GalaxyView({ events, fullscreen = false }) {
  const mountRef = useRef(null);
  const visibleEvents = useMemo(() => events.slice(0, MAX_RENDER_EVENTS), [events]);

  useEffect(() => {
    const mount = mountRef.current;
    if (!mount) {
      return undefined;
    }

    const width = mount.clientWidth || 720;
    const height = fullscreen ? Math.max(window.innerHeight - 140, 520) : 420;

    const scene = new THREE.Scene();
    scene.fog = new THREE.Fog(0x08111f, 12, 30);

    const camera = new THREE.PerspectiveCamera(60, width / height, 0.1, 1000);
    camera.position.set(0, 2.5, 13);

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));

    mount.innerHTML = '';
    mount.appendChild(renderer.domElement);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.055;
    controls.rotateSpeed = 0.75;
    controls.zoomSpeed = 0.7;
    controls.enablePan = false;
    controls.minDistance = 7;
    controls.maxDistance = 30;

    const ambient = new THREE.AmbientLight(0xffffff, 0.8);
    scene.add(ambient);

    const pointLight = new THREE.PointLight(0x66d9ff, 2.6, 100);
    pointLight.position.set(6, 8, 10);
    scene.add(pointLight);

    const backLight = new THREE.PointLight(0x7d68ff, 1.5, 90);
    backLight.position.set(-7, -4, -8);
    scene.add(backLight);

    const backgroundStars = new THREE.BufferGeometry();
    const starPositions = [];
    for (let index = 0; index < 1200; index += 1) {
      starPositions.push((Math.random() - 0.5) * 60);
      starPositions.push((Math.random() - 0.5) * 60);
      starPositions.push((Math.random() - 0.5) * 60);
    }
    backgroundStars.setAttribute('position', new THREE.Float32BufferAttribute(starPositions, 3));
    const starMaterial = new THREE.PointsMaterial({
      color: 0xe8edff,
      size: 0.05,
      transparent: true,
      opacity: 0.95,
      depthWrite: false,
    });
    const starField = new THREE.Points(backgroundStars, starMaterial);
    scene.add(starField);

    const hazeGeometry = new THREE.BufferGeometry();
    const hazePositions = [];
    for (let index = 0; index < 450; index += 1) {
      const radius = 6 + Math.random() * 10;
      const theta = Math.random() * Math.PI * 2;
      const y = (Math.random() - 0.5) * 6;
      hazePositions.push(Math.cos(theta) * radius, y, Math.sin(theta) * radius);
    }
    hazeGeometry.setAttribute('position', new THREE.Float32BufferAttribute(hazePositions, 3));
    const hazeMaterial = new THREE.PointsMaterial({
      color: 0x6f7dfd,
      size: 0.09,
      transparent: true,
      opacity: 0.25,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });
    const haze = new THREE.Points(hazeGeometry, hazeMaterial);
    scene.add(haze);

    const nodes = [];
    const trails = [];
    const createNode = (event, index) => {
      const geometry = new THREE.SphereGeometry(0.24 + ((index % 3) * 0.06), 20, 20);
      const eventType = event.event?.event_type || event.event_type;
      const eventColor = COLOR_MAP[eventType] || 0xffffff;
      const material = new THREE.MeshStandardMaterial({
        color: eventColor,
        emissive: eventColor,
        emissiveIntensity: 0.42,
        metalness: 0.12,
        roughness: 0.35,
      });
      const mesh = new THREE.Mesh(geometry, material);
      const radius = 3.8 + Math.random() * 4.1;
      const angle = (index / Math.max(visibleEvents.length, 1)) * Math.PI * 2;
      mesh.position.set(
        Math.cos(angle) * radius,
        (Math.random() - 0.5) * 4,
        Math.sin(angle) * radius
      );
      nodes.push(mesh);
      scene.add(mesh);

      const trailGeometry = new THREE.BufferGeometry();
      const trailPoints = new Float32Array(18);
      for (let idx = 0; idx < trailPoints.length; idx += 3) {
        trailPoints[idx] = mesh.position.x;
        trailPoints[idx + 1] = mesh.position.y;
        trailPoints[idx + 2] = mesh.position.z;
      }
      trailGeometry.setAttribute('position', new THREE.BufferAttribute(trailPoints, 3));
      const trailMaterial = new THREE.LineBasicMaterial({
        color: eventColor,
        transparent: true,
        opacity: 0.28,
        blending: THREE.AdditiveBlending,
      });
      const trail = new THREE.Line(trailGeometry, trailMaterial);
      trails.push(trail);
      scene.add(trail);
    };

    visibleEvents.forEach(createNode);

    const coreGeometry = new THREE.SphereGeometry(1.25, 32, 32);
    const coreMaterial = new THREE.MeshStandardMaterial({
      color: 0xb8c5ff,
      emissive: 0x4f6dff,
      emissiveIntensity: 0.9,
      metalness: 0.22,
      roughness: 0.3,
    });
    const core = new THREE.Mesh(coreGeometry, coreMaterial);
    scene.add(core);

    const coreGlow = new THREE.Sprite(
      new THREE.SpriteMaterial({
        color: 0x8fa2ff,
        transparent: true,
        opacity: 0.42,
        blending: THREE.AdditiveBlending,
      })
    );
    coreGlow.scale.set(6.2, 6.2, 1);
    scene.add(coreGlow);

    const clock = new THREE.Clock();

    let frame = 0;
    const animate = () => {
      frame = requestAnimationFrame(animate);
      const elapsed = clock.getElapsedTime();
      controls.update();
      core.rotation.x += 0.012;
      core.rotation.y += 0.018;
      coreGlow.material.opacity = 0.32 + Math.sin(elapsed * 2.4) * 0.14;
      starField.rotation.y += 0.0014;
      haze.rotation.y -= 0.0008;
      nodes.forEach((node, index) => {
        node.rotation.x += 0.016 + (index % 4) * 0.002;
        node.rotation.y += 0.021;
        node.position.y += Math.sin(elapsed * 2.0 + index) * 0.0011;

        const trail = trails[index];
        const attr = trail.geometry.attributes.position;
        for (let i = attr.count - 1; i > 0; i -= 1) {
          attr.setXYZ(i, attr.getX(i - 1), attr.getY(i - 1), attr.getZ(i - 1));
        }
        attr.setXYZ(0, node.position.x, node.position.y, node.position.z);
        attr.needsUpdate = true;
      });
      renderer.render(scene, camera);
    };
    animate();

    const onResize = () => {
      const nextWidth = mount.clientWidth || width;
      const nextHeight = fullscreen ? Math.max(window.innerHeight - 140, 520) : height;
      renderer.setSize(nextWidth, nextHeight);
      camera.aspect = nextWidth / nextHeight;
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
      controls.dispose();
      mount.innerHTML = '';
    };
  }, [fullscreen, visibleEvents]);

  return <div className="galaxy-view" ref={mountRef} />;
}
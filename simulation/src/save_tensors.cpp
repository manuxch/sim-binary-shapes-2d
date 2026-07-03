void save_tensors(b2World *w, int n_frame, const GlobalSetup *globalSetup,
                  double *pmin, double *pmax, double tSim) {
  string file_name = "frames_" + globalSetup->dirID + "/" +
                     globalSetup->preFrameFile + "_" + int2str(n_frame) +
                     ".sxy";
  std::ofstream fout;
  fout.open(file_name.c_str());
  fout << "# tSim: " << tSim << endl;
  fout << "# gID stres.xx stres.xy stres.yx stres.yy " << endl;
  b2Body *body_A, *body_B;
  BodyData *bd_data_A, *bd_data_B;
  b2Vec2 l_A, l_B, force_N, force_T, force, c_point;
  float normal_impulse, tangential_impulse, area_a, area_b;
  std::map<uint32_t, Tensor> stress_tensors;

  // Recorrer cuerpos para inicializar
    for (b2Body *body = w->GetBodyList(); body; body = body->GetNext()) {
        if (body->GetType() != b2_dynamicBody) continue;
        BodyData *bd = (BodyData *)(body->GetUserData()).pointer;
        if (!inROI(body->GetPosition(), globalSetup)) continue;
        if (bd->isGrain) {
            stress_tensors[bd->gID] = {0, 0, 0, 0};  // Inicializa en cero
        }
    }
  for (b2Contact *c = w->GetContactList(); c; c = c->GetNext()) {
    if (c->IsTouching()) {
      b2WorldManifold world_manifold;
      c->GetWorldManifold(&world_manifold);
      body_A = c->GetFixtureA()->GetBody();
      body_B = c->GetFixtureB()->GetBody();
      bd_data_A = (BodyData *)(body_A->GetUserData()).pointer;
      bd_data_B = (BodyData *)(body_B->GetUserData()).pointer;
      area_a = get_body_area(body_A);
      area_b = get_body_area(body_B);

      for (int32 i = 0; i < c->GetManifold()->pointCount; ++i) {
        c_point = world_manifold.points[i];
        normal_impulse = c->GetManifold()->points[i].normalImpulse;
        tangential_impulse = c->GetManifold()->points[i].tangentImpulse;
        // Normal apunta del body_A al body_B
        force_N = -normal_impulse * world_manifold.normal;
        force_T = -tangential_impulse *
                  b2Vec2(-world_manifold.normal.y, world_manifold.normal.x);
        force = (1.0 / globalSetup->tStep) *
                (force_N + force_T); // impulso -> fuerza
        l_A = c_point - body_A->GetWorldCenter();
        l_B = c_point - body_B->GetWorldCenter();
        if (bd_data_A->isGrain) {
            auto it = stress_tensors.find(bd_data_A->gID);
            if (it != stress_tensors.end()) {
                Tensor& tensor_A = it->second;
                tensor_A.xx += force.x * l_A.x / area_a;
                tensor_A.xy += force.x * l_A.y / area_a;
                tensor_A.yx += force.y * l_A.x / area_a;
                tensor_A.yy += force.y * l_A.y / area_a;
            }
        }
        if (bd_data_B->isGrain) {
            auto it = stress_tensors.find(bd_data_B->gID);
            if (it != stress_tensors.end()) {
                Tensor& tensor_B = it->second;
                tensor_B.xx -= force.x * l_B.x / area_b;
                tensor_B.xy -= force.x * l_B.y / area_b;
                tensor_B.yx -= force.y * l_B.x / area_b;
                tensor_B.yy -= force.y * l_B.y / area_b;
            }
        }
      }
    }
  }
  // Escribir resultados (solo granos que tienen contactos)
  double pressure;
  for (const auto& [gID, tensor] : stress_tensors) {
    fout << gID << " " << tensor.xx << " " << tensor.xy
         << " " << tensor.yx << " " << tensor.yy << " " << endl;

    pressure = -0.5 * (tensor.xx + tensor.yy);
    if (pressure < *pmin) *pmin = pressure;
    if (pressure > *pmax) *pmax = pressure;
  }

  fout << std::flush;
  fout.close();
}

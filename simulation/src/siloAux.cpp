/*! \file siloAux.cpp
 * \brief Archivo de implementación de funciones auxiliares
 *
 * \author Manuel Carlevaro <manuel@iflysib.unlp.edu.ar>
 *
 * \version 1.0 Versión inicial
 *
 * \date 2022.07.25
 */

#include "siloAux.hpp"

std::string int2str(int num) {
    std::ostringstream oss;
    oss << std::setfill('0') << std::setw(6) << num;
    return oss.str();
}

bool isActive(b2World *w) {
    // BodyData* infGr;
    for (b2Body *bd = w->GetBodyList(); bd; bd = bd->GetNext()) {
        // infGr = (BodyData*) (bd->GetUserData()).pointer;
        if (bd->IsAwake()) return true;
        // if (infGr->isGrain && infGr->isIn && bd->IsAwake()) return true;
    }
    return false;
}

void savePart(b2World *w, int file_id, const GlobalSetup *globalSetup) {
    string file_name = "frames_" + globalSetup->dirID +
        "/particles_info_" + int2str(file_id) + ".dat";
    std::ofstream ff;
    ff.open(file_name.c_str());
    BodyData* infGr;
    b2Vec2 p; float angle;
    for (b2Body *bd = w->GetBodyList(); bd; bd = bd->GetNext()) {
        infGr = (BodyData*) (bd->GetUserData()).pointer;
        if (infGr->isGrain) {
            p = bd->GetPosition();
            angle = bd->GetAngle();
            ff << infGr->gID << " " << p.x << " " << p.y << " " << angle 
                << " " << endl;
        }
    }
    ff << std::flush;
    ff.close();
}

void saveFrame(b2World *w, int frm_id, const GlobalSetup *globalSetup) {

    std::string file_name = "frames_" + globalSetup->dirID + "/"
    + globalSetup->preFrameFile + "_" + int2str(frm_id) + ".xy";

    std::ofstream fileF;
    fileF.open(file_name.c_str());

    for (b2Body* bd = w->GetBodyList(); bd; bd = bd->GetNext()) {

        BodyData* infGr = (BodyData*) (bd->GetUserData()).pointer;

        // -----------------------------------
        //   GRANOS (discos o polígonos)
        // -----------------------------------
        if (infGr->isGrain) {

            // id del grano
            fileF << infGr->gID << " ";

            // ----- Polígonos (nLados > 1) -----
            if (infGr->nLados > 1) {
                b2Fixture* f = bd->GetFixtureList();
                b2PolygonShape* poly = (b2PolygonShape*) f->GetShape();
                int count = poly->m_count;

                // número de vértices
                fileF << count << " ";

                b2Vec2* verts = poly->m_vertices;
                for (int i = 0; i < count; ++i) {
                    b2Vec2 wp = bd->GetWorldPoint(verts[i]);
                    fileF << wp.x << " " << wp.y << " ";
                }
            }
            // ----- Discos (nLados == 1) -----
            else if (infGr->nLados == 1) {
                b2Fixture* f = bd->GetFixtureList();
                b2CircleShape* cs = (b2CircleShape*) f->GetShape();
                b2Vec2 pos = bd->GetPosition();
                float radio = cs->m_radius;

                // nVerts = 1
                fileF << 1 << " ";
                fileF << pos.x << " " << pos.y << " " << radio << " ";
            }

            // tipo (para el color)
            fileF << infGr->tipo << " ";
            fileF << std::endl;
        }

        // -----------------------------------
        //   TAPA (gID = -110 o -120)
        // -----------------------------------
        else if (infGr->gID == -110 || infGr->gID == -120) {
            b2Fixture* f = bd->GetFixtureList();
            b2EdgeShape* s = (b2EdgeShape*) f->GetShape();
            b2Vec2 verts[2];

            verts[0] = s->m_vertex1;
            verts[1] = s->m_vertex2;

            fileF << infGr->gID << " ";
            fileF << 2 << " ";

            verts[0] = bd->GetWorldPoint(verts[0]);
            fileF << verts[0].x << " " << verts[0].y << " ";

            verts[1] = bd->GetWorldPoint(verts[1]);
            fileF << verts[1].x << " " << verts[1].y << " ";

            fileF << (infGr->gID == -110 ? "LID-F" : "LID-W") << std::endl;
        }

        // -----------------------------------
        //   PAREDES / CAJA (resto de IDs negativos)
        // -----------------------------------
        else {
            for (b2Fixture* f = bd->GetFixtureList(); f; f = f->GetNext()) {
                fileF << infGr->gID << " ";

                b2ChainShape* s = (b2ChainShape*) f->GetShape();
                b2Vec2* verts = (b2Vec2*) s->m_vertices;

                fileF << s->m_count << " ";
                for (int i = 0; i < s->m_count; ++i) {
                    verts[i] = bd->GetWorldPoint(verts[i]);
                    fileF << verts[i].x << " " << verts[i].y << " ";
                }
                fileF << "BOX" << std::endl;
            }
        }
    }

    fileF.close();
}


int countDesc(b2World *w, int *st, int paso, 
        std::ofstream &fluxFile, const GlobalSetup* gs) {
    int granoDesc = 0; // Granos totales descargados en la trayectoria
    double tStep = gs->tStep;
    for (int i = 0; i < gs->noTipoGranos; ++i) granoDesc += st[i];
    BodyData* infGr;
    b2Vec2 p, p_aux, p_0hole, pv;
    double y_min = gs->caja.y_max_hole;
    double radio;
    p_0hole.Set(0.0f, 0.5f * y_min);
    double nout_x = gs->caja.n_out.x;
    double nout_y = gs->caja.n_out.y;
    int nGranos = 0; // granos descargados en este check
    //int sumaTotal = 0;
    for (b2Body *bd = w->GetBodyList(); bd; bd = bd->GetNext()) {
        infGr = (BodyData*) (bd->GetUserData()).pointer;
        if (infGr->isGrain && infGr->isIn) {
            p = bd->GetPosition();
            if (p.y > y_min) continue;
            b2Fixture *fixt = bd->GetFixtureList();
            b2Shape *shape = fixt->GetShape();
            if (infGr->nLados == 1) {
                radio = shape->m_radius;
            }
            else {
                b2PolygonShape *poly = (b2PolygonShape*) shape;
                b2Vec2* verts = (b2Vec2*) poly->m_vertices;
                pv = b2Vec2(verts[0].x - p.x, verts[0].y - p.y);
                radio = pv.Length();
            }
            p_aux = p - p_0hole;
            if (p.y - radio < 0.0f || nout_x * p_aux.x + nout_y * p_aux.y > radio) {
                infGr->isIn = false;
                nGranos++;
                granoDesc++;
                st[infGr->tipo]++;
                fluxFile << granoDesc << " " << infGr->tipo << " ";
                fluxFile << std::setprecision(5) << paso * tStep << " ";
                for (int i = 0; i < gs->noTipoGranos; ++i) {
                    //sumaTotal += st[i];
                    fluxFile << st[i] << " ";
                }
                fluxFile << granoDesc << endl;
            }            
        }
    }
    return nGranos;
}

void printVE(int frm_id, float timeS, b2World *w, const GlobalSetup* gs) {
    b2Vec2 pi, vi; 
    float wi, mi, Ii, vim;
    b2Vec2 vt(0.0, 0.0);
    string file_name = "frames_" + gs->dirID + "/"
        + "ve_" + int2str(frm_id) + ".dat";
    std::ofstream fileF;
    fileF.open(file_name.c_str());
    fileF << "# gID type x y vx vy w E_kin_lin E_kin_rot "
        << " ## sim_time: " << timeS << endl;
    for (b2Body *bi = w->GetBodyList(); bi; bi = bi->GetNext()) {
        BodyData *igi = (BodyData*) (bi->GetUserData()).pointer;
        if (!igi->isGrain) {
            continue;
        }
        pi = bi->GetPosition();
        vi = bi->GetLinearVelocity();
        vim = vi.Length();
        wi = bi->GetAngularVelocity();
        mi = bi->GetMass();
        Ii = bi->GetInertia();
        fileF << igi->gID << " " << igi->tipo << " " 
            << pi.x << " " << pi.y << " " 
            << vi.x << " " << vi.y << " " << wi << " "
            << 0.5 * mi * vim * vim << " "
            << 0.5 * Ii * wi * wi << endl;
    }
    fileF.close();
}


void saveContacts(b2World *w, float ts, int file_id, const GlobalSetup *globalSetup) {
    string file_name = "frames_" + globalSetup->dirID +
        "/force_contact_" + int2str(file_id) + ".dat";
    std::ofstream ff;
    ff.open(file_name.c_str());
    float norm, tang;
    for (b2Contact *c = w->GetContactList(); c; c = c->GetNext()) {
        if (!c->IsTouching()) continue;
        int numPoints = c->GetManifold()->pointCount;
        b2WorldManifold worldManifold;
        c->GetWorldManifold(&worldManifold);
        b2Body *bodyA = c->GetFixtureA()->GetBody();
        b2Body *bodyB = c->GetFixtureB()->GetBody();
        BodyData *bdgdA, *bdgdB;
        bdgdA = (BodyData*)(bodyA->GetUserData()).pointer;
        bdgdB = (BodyData*)(bodyB->GetUserData()).pointer;
        for (int i = 0; i < numPoints; i++) {
            ff << bdgdA->gID << " " << bdgdB->gID << " "
                  << worldManifold.points[i].x << " " 
                  << worldManifold.points[i].y << " ";
            norm = (c->GetManifold())->points[i].normalImpulse;
            tang = (c->GetManifold())->points[i].tangentImpulse;
            ff << norm/ts << " " << fabs(tang)/ts
                  << " CP" << numPoints << endl;
        }
    }
    ff << std::flush;
    ff.close();
}

void saveQ6(b2World *w, int file_id, const GlobalSetup *globalSetup) {
    string file_name = "frames_" + globalSetup->dirID +
        "/q6_" + int2str(file_id) + ".dat";
    std::ofstream ff;
    ff.open(file_name.c_str());
    ff << "# Step: " << file_id << endl;
    ff << "# id x y Q6" << endl;
    double zero = 0.0;
    double P0=gsl_sf_legendre_sphPlm(6, 0, zero);
    double P1=gsl_sf_legendre_sphPlm(6, 1, zero);
    double P2=gsl_sf_legendre_sphPlm(6, 2, zero);
    double P3=gsl_sf_legendre_sphPlm(6, 3, zero);
    double P4=gsl_sf_legendre_sphPlm(6, 4, zero);
    double P5=gsl_sf_legendre_sphPlm(6, 5, zero);
    double P6=gsl_sf_legendre_sphPlm(6, 6, zero);

    // Primer cuerpo del mundo
    b2Body* bd_ref = w->GetBodyList();
    BodyData *bd_ref_data;
    b2Vec2 p_ref, p_ctt, p_rel;
    int nc = 0; // número de contactos del cuerpo

    // Recorre todos los cuerpos del mundo
    while (bd_ref) {
        //b2Body* cuerpoDado = cuerpoActual;
        std::vector<b2Body*> bd_contact_list;

        // Recorre todos los contactos en el mundo
        for (b2Contact* contacto = w->GetContactList(); contacto; contacto = contacto->GetNext()) {
            b2Fixture* fixtureA = contacto->GetFixtureA();
            b2Fixture* fixtureB = contacto->GetFixtureB();

            b2Body* cuerpoA = fixtureA->GetBody();
            b2Body* cuerpoB = fixtureB->GetBody();

            if ((cuerpoA == bd_ref) && (cuerpoB->GetType() == b2_dynamicBody)) {
                bd_contact_list.push_back(cuerpoB);
            }
            else if ((cuerpoB == bd_ref) && (cuerpoA->GetType() == b2_dynamicBody)) {
                bd_contact_list.push_back(cuerpoA);
            }
        }

        // Recorremos los contactos de bd_ref y calculamos el Q6
        p_ref = bd_ref->GetPosition();
        nc = 0;
        double Q0r = 0.0, Q0i = 0.0, Q1r = 0.0, Q1i = 0.0, Q2r = 0.0, Q2i = 0.0;
        double Q3r = 0.0, Q3i = 0.0, Q4r = 0.0, Q4i = 0.0, Q5r = 0.0, Q5i = 0.0;
        double Q6r = 0.0, Q6i = 0.0;
        double Q = 0.0;
        double phi;
        for (b2Body* bd_in_contact : bd_contact_list) {
            // Realiza las operaciones necesarias con cada cuerpo en contacto
            p_ctt = bd_in_contact->GetPosition();
            p_rel = p_ctt - p_ref;
            phi = atan2(p_rel.y, p_rel.x);
            Q0r += cos(0.0 * phi); Q0i += sin(0.0 * phi);
            Q1r += cos(1.0 * phi); Q1i += sin(1.0 * phi);
            Q2r += cos(2.0 * phi); Q2i += sin(2.0 * phi);
            Q3r += cos(3.0 * phi); Q3i += sin(3.0 * phi);
            Q4r += cos(4.0 * phi); Q4i += sin(4.0 * phi);
            Q5r += cos(5.0 * phi); Q5i += sin(5.0 * phi);
            Q6r += cos(6.0 * phi); Q6i += sin(6.0 * phi);
        }
        nc = bd_contact_list.size();
        if (nc) {
            nc *= nc;
            Q = P0 * P0 * (Q0r * Q0r + Q0i * Q0i) / nc +
                2.0 * P1 * P1 * (Q1r * Q1r + Q1i * Q1i) / nc +
                2.0 * P2 * P2 * (Q2r * Q2r + Q2i * Q2i) / nc +
                2.0 * P3 * P3 * (Q3r * Q3r + Q3i * Q3i) / nc +
                2.0 * P4 * P4 * (Q4r * Q4r + Q4i * Q4i) / nc +
                2.0 * P5 * P5 * (Q5r * Q5r + Q5i * Q5i) / nc +
                2.0 * P6 * P6 * (Q6r * Q6r + Q6i * Q6i) / nc;

            bd_ref_data = (BodyData*)(bd_ref->GetUserData()).pointer;
            ff << bd_ref_data->gID << " " << p_ref.x << " " << p_ref.y << " " << Q << endl;
        }

        // Siguiente cuerpo del mundo
        bd_ref = bd_ref->GetNext();
    }
    ff << std::flush;
    ff.close();
}

//void savePF(b2World *w, int file_id, const GlobalSetup *globalSetup) {
    //string file_name = "frames_" + globalSetup->dirID +
        //"/q6_" + int2str(file_id) + ".dat";
    //std::ofstream ff;
    //ff.open(file_name.c_str());
    //ff << "# Step: " << file_id << endl;
    //ff << "# x y PF" << endl;
    //b2Vec2 pos;
    //BodyData *bd_data;

    //// Creo un conjunto de puntos
    //std::vector<Kernel::Point_2> points;
    //std::vector<double> radii;
    //for (b2Body *bd = w->GetBodyList(); bd; bd = bd->GetNext()) {
        //if (bd->GetType() != b2_dynamicBody) continue;
        //pos = bd->GetPosition();
        //points.push_back(Kernel::Point_2(pos.x, pos.y));
        //bd_data = (BodyData*)(bd->GetUserData()).pointer;
        //radii-push_back(bd_data.radio)
    //}
    //// Calculo la red de Voronoi 
    //VoronoiDiagram vd;
    //vd.insert(points.begin(), points.end());
    //// Calculo la red dual
    //Dual dual;
    //vd.dual(dual);




    //// Primer cuerpo del mundo
    //b2Body* bd_ref = w->GetBodyList();
    //BodyData *bd_ref_data;
    //b2Vec2 p_ref, p_ctt, p_rel;
    //int nc = 0; // número de contactos del cuerpo

    //// Recorre todos los cuerpos del mundo
    //while (bd_ref) {
        ////b2Body* cuerpoDado = cuerpoActual;
        //std::vector<b2Body*> bd_contact_list;

        //// Recorre todos los contactos en el mundo
        //for (b2Contact* contacto = w->GetContactList(); contacto; contacto = contacto->GetNext()) {
            //b2Fixture* fixtureA = contacto->GetFixtureA();
            //b2Fixture* fixtureB = contacto->GetFixtureB();

            //b2Body* cuerpoA = fixtureA->GetBody();
            //b2Body* cuerpoB = fixtureB->GetBody();

            //if ((cuerpoA == bd_ref) && (cuerpoB->GetType() == b2_dynamicBody)) {
                //bd_contact_list.push_back(cuerpoB);
            //}
            //else if ((cuerpoB == bd_ref) && (cuerpoA->GetType() == b2_dynamicBody)) {
                //bd_contact_list.push_back(cuerpoA);
            //}
        //}

        //// Recorremos los contactos de bd_ref y calculamos el Q6
        //p_ref = bd_ref->GetPosition();
        //nc = 0;
        //double Q0r = 0.0, Q0i = 0.0, Q1r = 0.0, Q1i = 0.0, Q2r = 0.0, Q2i = 0.0;
        //double Q3r = 0.0, Q3i = 0.0, Q4r = 0.0, Q4i = 0.0, Q5r = 0.0, Q5i = 0.0;
        //double Q6r = 0.0, Q6i = 0.0;
        //double Q = 0.0;
        //double phi;
        //for (b2Body* bd_in_contact : bd_contact_list) {
            //// Realiza las operaciones necesarias con cada cuerpo en contacto
            //p_ctt = bd_in_contact->GetPosition();
            //p_rel = p_ctt - p_ref;
            //phi = atan2(p_rel.y, p_rel.x);
            //Q0r += cos(0.0 * phi); Q0i += sin(0.0 * phi);
            //Q1r += cos(1.0 * phi); Q1i += sin(1.0 * phi);
            //Q2r += cos(2.0 * phi); Q2i += sin(2.0 * phi);
            //Q3r += cos(3.0 * phi); Q3i += sin(3.0 * phi);
            //Q4r += cos(4.0 * phi); Q4i += sin(4.0 * phi);
            //Q5r += cos(5.0 * phi); Q5i += sin(5.0 * phi);
            //Q6r += cos(6.0 * phi); Q6i += sin(6.0 * phi);
        //}
        //nc = bd_contact_list.size();
        //if (nc) {
            //nc *= nc;
            //Q = P0 * P0 * (Q0r * Q0r + Q0i * Q0i) / nc +
                //2.0 * P1 * P1 * (Q1r * Q1r + Q1i * Q1i) / nc +
                //2.0 * P2 * P2 * (Q2r * Q2r + Q2i * Q2i) / nc +
                //2.0 * P3 * P3 * (Q3r * Q3r + Q3i * Q3i) / nc +
                //2.0 * P4 * P4 * (Q4r * Q4r + Q4i * Q4i) / nc +
                //2.0 * P5 * P5 * (Q5r * Q5r + Q5i * Q5i) / nc +
                //2.0 * P6 * P6 * (Q6r * Q6r + Q6i * Q6i) / nc;

            //bd_ref_data = (BodyData*)(bd_ref->GetUserData()).pointer;
            //ff << bd_ref_data->gID << " " << p_ref.x << " " << p_ref.y << " " << Q << endl;
        //}

        //// Siguiente cuerpo del mundo
        //bd_ref = bd_ref->GetNext();
    //}
    //ff << std::flush;
    //ff.close();
//}
